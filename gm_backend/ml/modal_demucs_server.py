"""GPU Demucs service exposed from the shared gm-music-server Modal app.

The controller endpoint does not load Demucs or a GPU. It only claims an
idempotent job and spawns the GPU worker class. The public request/response
contract is intentionally compatible with the previous MusicGen endpoint.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import boto3
import modal

try:
    from .modal_app import app
except ImportError:  # Modal executes the file from its source directory.
    from modal_app import app


controller_image = (
    modal.Image.debian_slim()
    .pip_install(
        "fastapi[standard]",
        "boto3",
        "pydantic",
    )
    .add_local_file(
        str(Path(__file__).with_name("modal_app.py")),
        remote_path="/root/modal_app.py",
    )
)

demucs_image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg")
    .pip_install(
        "demucs==4.0.1",
        "numpy==1.26.4",
        "boto3",
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "torchcodec==0.7.0",
        # Backend de torchaudio para guardar los WAV de Demucs: sin él, con el FFmpeg de
        # debian_slim falla con "Couldn't find appropriate backend to handle uri ... vocals.wav".
        "soundfile==0.13.1",
    )
    .add_local_file(
        str(Path(__file__).with_name("modal_app.py")),
        remote_path="/root/modal_app.py",
    )
)

music_gen_secrets = modal.Secret.from_name("music-gen-secret")
stem_job_status = modal.Dict.from_name("gm-stem-job-status", create_if_missing=True)

JOB_TTL_SECONDS = int(os.environ.get("DEMUCS_JOB_TTL_SECONDS", "3600"))
SPAWN_LEASE_SECONDS = int(os.environ.get("DEMUCS_SPAWN_LEASE_SECONDS", "300"))
PROCESSING_STALE_SECONDS = int(
    os.environ.get("DEMUCS_PROCESSING_STALE_SECONDS", "1800")
)
WORKER_LEASE_SECONDS = PROCESSING_STALE_SECONDS + 120
STATUS_UPDATE_LOCK_SECONDS = 30
STATUS_UPDATE_LOCK_WAIT_SECONDS = 2
ALLOW_SYNC = os.environ.get("DEMUCS_ALLOW_SYNC", "false").lower() in {
    "1",
    "true",
    "yes",
}


def _worker_owns_job(job_id: str, lease_id: str | None) -> bool:
    if not lease_id:
        return True
    lease = stem_job_status.get(f"worker:{job_id}")
    return isinstance(lease, dict) and lease.get('lease_id') == lease_id


def _worker_can_fail_job(job_id: str, lease_id: str | None) -> bool:
    """Allow the current spawn lease to publish pre-worker failures."""
    if _worker_owns_job(job_id, lease_id):
        return True
    spawn_lease = stem_job_status.get(f"spawn:{job_id}")
    return bool(
        lease_id
        and isinstance(spawn_lease, dict)
        and spawn_lease.get('lease_id') == lease_id
    )
GPU_CONFIG = os.environ.get("DEMUCS_GPU", "T4")


def _now() -> int:
    return int(time.time())


def _get_r2_storage():
    required = (
        "R2_ENDPOINT",
        "R2_REGION",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_DOCUMENTS_BUCKET",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Faltan variables R2 en el secreto de Modal: " + ", ".join(missing))

    return (
        boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT"],
            region_name=os.environ["R2_REGION"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        ),
        os.environ["R2_DOCUMENTS_BUCKET"],
    )


def _set_status(job_id: str, **values):
    lock_key = f"status-update:{job_id}"
    lock_id = str(uuid.uuid4())
    deadline = time.time() + STATUS_UPDATE_LOCK_WAIT_SECONDS

    while time.time() < deadline:
        existing_lock = stem_job_status.get(lock_key)
        if isinstance(existing_lock, dict) and existing_lock.get("expires_at", 0) <= _now():
            reclaim_key = f"status-reclaim:{job_id}"
            if stem_job_status.put(
                reclaim_key,
                {"created_at": _now(), "expires_at": _now() + STATUS_UPDATE_LOCK_SECONDS},
                skip_if_exists=True,
            ):
                try:
                    latest_lock = stem_job_status.get(lock_key)
                    if isinstance(latest_lock, dict) and latest_lock.get("expires_at", 0) <= _now():
                        stem_job_status.pop(lock_key, None)
                finally:
                    stem_job_status.pop(reclaim_key, None)

        acquired = stem_job_status.put(
            lock_key,
            {
                "lock_id": lock_id,
                "created_at": _now(),
                "expires_at": _now() + STATUS_UPDATE_LOCK_SECONDS,
            },
            skip_if_exists=True,
        )
        if acquired:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError(f"No se pudo actualizar el estado del job {job_id}: lock ocupado.")

    try:
        current = stem_job_status.get(job_id, {})
        current.update(values)
        current["updated_at"] = _now()
        stem_job_status[job_id] = current
    finally:
        current_lock = stem_job_status.get(lock_key)
        if isinstance(current_lock, dict) and current_lock.get("lock_id") == lock_id:
            stem_job_status.pop(lock_key, None)


def _status(job_id: str):
    value = stem_job_status.get(job_id)
    if not value:
        return None
    if value.get("expires_at", 0) < _now():
        try:
            stem_job_status.pop(job_id, None)
            client_job_id = value.get("client_job_id")
            if client_job_id:
                stem_job_status.pop(f"client:{client_job_id}", None)
        except Exception:
            pass
        return None
    return value


def _validate_key(s3_key: str) -> str:
    if not isinstance(s3_key, str) or not s3_key.strip():
        raise ValueError("s3_key es obligatorio.")
    key = s3_key.strip()
    if key.startswith("/") or ".." in Path(key).parts:
        raise ValueError("s3_key no es válido.")
    return key


def _claim_job(client_job_id: str | None) -> str:
    if not client_job_id:
        job_id = str(uuid.uuid4())
        stem_job_status[job_id] = {
            "status": "queued",
            "progress_pct": 0,
            "stems": {},
            "error_message": None,
            "expires_at": _now() + JOB_TTL_SECONDS,
        }
        return job_id

    client_key = f"client:{client_job_id}"
    existing = stem_job_status.get(client_key)
    if existing:
        existing_id = existing.get("job_id") if isinstance(existing, dict) else existing
        if existing_id and _status(existing_id):
            return existing_id

        recovery_key = f"client-recover:{client_job_id}"
        recovered = stem_job_status.put(
            recovery_key,
            {"created_at": _now(), "expires_at": _now() + SPAWN_LEASE_SECONDS},
            skip_if_exists=True,
        )
        if not recovered:
            latest = stem_job_status.get(client_key)
            latest_id = latest.get("job_id") if isinstance(latest, dict) else latest
            if latest_id and _status(latest_id):
                return latest_id
            raise RuntimeError("El client_job_id está siendo recuperado; reintente.")
        try:
            latest = stem_job_status.get(client_key)
            latest_id = latest.get("job_id") if isinstance(latest, dict) else latest
            if latest_id and _status(latest_id):
                return latest_id
            stem_job_status.pop(client_key, None)
        finally:
            stem_job_status.pop(recovery_key, None)

    job_id = str(uuid.uuid4())
    lease_id = str(uuid.uuid4())
    claim = {
        "job_id": job_id,
        "state": "initializing",
        "created_at": _now(),
        "lease_id": lease_id,
        "expires_at": _now() + JOB_TTL_SECONDS,
    }
    # skip_if_exists is the atomic compare-and-set supported by Modal Dict.
    claimed = stem_job_status.put(client_key, claim, skip_if_exists=True)
    if not claimed:
        existing = stem_job_status.get(client_key)
        existing_id = existing.get("job_id") if isinstance(existing, dict) else existing
        if existing_id:
            return existing_id
        raise RuntimeError("No se pudo reclamar el job Demucs.")

    stem_job_status[job_id] = {
        "status": "queued",
        "progress_pct": 0,
        "stems": {},
        "error_message": None,
        "client_job_id": client_job_id,
        "expires_at": _now() + JOB_TTL_SECONDS,
    }
    return job_id


def _ensure_job_status(job_id: str, client_job_id: str | None):
    current = _status(job_id)
    if current:
        return current
    values = {
        "status": "queued",
        "progress_pct": 0,
        "stems": {},
        "error_message": None,
        "expires_at": _now() + JOB_TTL_SECONDS,
    }
    if client_job_id:
        values["client_job_id"] = client_job_id
    stem_job_status[job_id] = values
    return values


def _spawn_if_needed(request: dict, job_id: str, _recovery=False):
    current = _ensure_job_status(job_id, request.get("client_job_id"))
    recovery_key = f"recover:{job_id}"
    if current.get("status") == "processing":
        worker_lease = stem_job_status.get(f"worker:{job_id}")
        if isinstance(worker_lease, dict) and worker_lease.get('expires_at', 0) > _now():
            return current
        updated_at = current.get('updated_at', 0)
        if updated_at and updated_at + PROCESSING_STALE_SECONDS > _now():
            return current
        if not _recovery:
            claimed_recovery = stem_job_status.put(
                recovery_key,
                {'created_at': _now(), 'expires_at': _now() + SPAWN_LEASE_SECONDS},
                skip_if_exists=True,
            )
            if not claimed_recovery:
                return current
            try:
                latest = _status(job_id)
                if latest and latest.get('status') == 'processing':
                    _set_status(job_id, status='queued', retryable=True)
                    return _spawn_if_needed(request, job_id, _recovery=True)
            finally:
                stem_job_status.pop(recovery_key, None)
            return current
    if current.get("status") == "queued" and not _recovery:
        if stem_job_status.get(recovery_key):
            return current
    if current.get("status") == "completed":
        return current
    if current.get("status") == "failed" and not current.get("retryable"):
        return current

    spawn_key = f"spawn:{job_id}"
    existing_lease = stem_job_status.get(spawn_key)
    if existing_lease:
        lease_expires_at = (
            existing_lease.get("expires_at", 0)
            if isinstance(existing_lease, dict)
            else 0
        )
        if lease_expires_at > _now():
            return current
        # La comprobación y eliminación del lease vencido también necesitan
        # exclusión: dos controladores no deben borrar y reclamar el mismo
        # lease simultáneamente.
        reclaim_key = f"reclaim:{job_id}"
        reclaimed = stem_job_status.put(
            reclaim_key,
            {'created_at': _now(), 'expires_at': _now() + SPAWN_LEASE_SECONDS},
            skip_if_exists=True,
        )
        if not reclaimed:
            return current
        try:
            latest_lease = stem_job_status.get(spawn_key)
            latest_expiry = (
                latest_lease.get('expires_at', 0)
                if isinstance(latest_lease, dict)
                else 0
            )
            if latest_expiry > _now():
                return current
            stem_job_status.pop(spawn_key, None)
        finally:
            stem_job_status.pop(reclaim_key, None)

    lease_id = str(uuid.uuid4())
    lease = {
        "created_at": _now(),
        "expires_at": _now() + SPAWN_LEASE_SECONDS,
        "lease_id": lease_id,
    }
    claimed = stem_job_status.put(
        spawn_key,
        lease,
        skip_if_exists=True,
    )
    if claimed:
        try:
            stem_job_status[job_id] = {
                **current,
                "status": "queued",
                "error_message": None,
                "retryable": False,
                "expires_at": _now() + JOB_TTL_SECONDS,
            }
            DemucsServer().process.spawn(request, job_id, lease_id)
        except Exception as exc:
            stem_job_status.pop(spawn_key, None)
            _set_status(job_id, status="failed", retryable=True, error_message=str(exc)[:500])
            raise
    return _status(job_id) or current



@app.cls(
    image=demucs_image,
    gpu=GPU_CONFIG,
    cpu=4.0,
    secrets=[music_gen_secrets],
    timeout=1800,
    scaledown_window=300,
)
class DemucsServer:

    @modal.method()
    def process(
        self,
        request: dict,
        job_id: str,
        lease_id: str | None = None,
    ):
        uploaded_keys: list[str] = []
        worker_lease_claimed = False
        worker_lease_id: str | None = None

        try:
            import demucs.separate
            import torch

            if not torch.cuda.is_available():
                raise RuntimeError(
                    "CUDA no está disponible para Demucs."
                )

            device_name = torch.cuda.get_device_name(
                torch.cuda.current_device()
            )

            # Comprobar que el controlador sigue siendo
            # propietario del lease de lanzamiento.
            spawn_lease = stem_job_status.get(f"spawn:{job_id}")

            if lease_id and (
                not isinstance(spawn_lease, dict)
                or spawn_lease.get("lease_id") != lease_id
            ):
                return

            worker_lease_id = lease_id or str(uuid.uuid4())

            # Impedir que dos workers procesen el mismo trabajo.
            worker_lease_claimed = stem_job_status.put(
                f"worker:{job_id}",
                {
                    "lease_id": worker_lease_id,
                    "created_at": _now(),
                    "expires_at": _now() + WORKER_LEASE_SECONDS,
                },
                skip_if_exists=True,
            )

            if not worker_lease_claimed:
                return

            _set_status(
                job_id,
                status="processing",
                progress_pct=10,
            )

            _set_status(
                job_id,
                device=device_name,
            )

            stem_job_status.pop(f"spawn:{job_id}", None)

            r2_client, bucket_name = _get_r2_storage()

            with tempfile.TemporaryDirectory(
                prefix=f"demucs-{job_id}-"
            ) as work_dir:

                source_path = Path(work_dir) / "source"
                wav_path = Path(work_dir) / "input.wav"
                output_dir = Path(work_dir) / "output"

                # Descargar audio original desde R2.
                r2_client.download_file(
                    bucket_name,
                    request["s3_key"],
                    str(source_path),
                )

                if source_path.stat().st_size <= 0:
                    raise ValueError(
                        "El objeto de audio está vacío."
                    )

                # Convertir el audio a WAV estéreo.
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v", "error",
                        "-y",
                        "-i", str(source_path),
                        "-ar", "44100",
                        "-ac", "2",
                        str(wav_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                if (
                    not wav_path.exists()
                    or wav_path.stat().st_size <= 0
                ):
                    raise ValueError(
                        "FFmpeg no produjo un WAV válido."
                    )

                _set_status(
                    job_id,
                    progress_pct=25,
                )

                # Ejecutar separación mediante Demucs.
                demucs.separate.main(
                    [
                        "--two-stems", "vocals",
                        "--device", "cuda",
                        "--out", str(output_dir),
                        str(wav_path),
                    ]
                )

                model_dir = (
                    output_dir
                    / "htdemucs"
                    / wav_path.stem
                )

                result: dict[str, str] = {}

                # Validar y subir las pistas a R2.
                for stem_type in ("vocals", "no_vocals"):

                    stem_path = (
                        model_dir / f"{stem_type}.wav"
                    )

                    if (
                        not stem_path.exists()
                        or stem_path.stat().st_size <= 0
                    ):
                        raise ValueError(
                            f"Demucs no produjo "
                            f"{stem_type}.wav válido."
                        )

                    key = f"stems/{job_id}/{stem_type}.wav"

                    r2_client.upload_file(
                        str(stem_path),
                        bucket_name,
                        key,
                    )

                    uploaded_keys.append(key)
                    result[stem_type] = key

                # Impedir que un worker antiguo publique
                # resultados si perdió su lease.
                if not _worker_owns_job(
                    job_id,
                    worker_lease_id,
                ):
                    for key in uploaded_keys:
                        r2_client.delete_object(
                            Bucket=bucket_name,
                            Key=key,
                        )
                    return

                # Publicar resultado exitoso.
                _set_status(
                    job_id,
                    status="completed",
                    progress_pct=100,
                    stems=result,
                    error_message=None,
                )

        except Exception as exc:

            # Determinar propiedad antes de liberar el lease.
            owns_job = _worker_can_fail_job(job_id, worker_lease_id)

            # Limpiar archivos parciales únicamente si
            # el worker todavía es propietario del trabajo.
            if owns_job:
                try:
                    r2_client, bucket_name = _get_r2_storage()

                    for key in uploaded_keys:
                        r2_client.delete_object(
                            Bucket=bucket_name,
                            Key=key,
                        )

                except Exception:
                    pass

                # Registrar fallo antes de liberar los leases.
                _set_status(
                    job_id,
                    status="failed",
                    progress_pct=0,
                    stems={},
                    error_message=str(exc)[:500],
                )

            raise

        finally:
            # Liberar únicamente los leases que
            # pertenecen a esta ejecución.
            if worker_lease_claimed:
                current_worker = stem_job_status.get(
                    f"worker:{job_id}"
                )

                if (
                    isinstance(current_worker, dict)
                    and current_worker.get("lease_id")
                    == worker_lease_id
                ):
                    stem_job_status.pop(
                        f"worker:{job_id}",
                        None,
                    )

            if lease_id:
                current_spawn = stem_job_status.get(
                    f"spawn:{job_id}"
                )

                if (
                    isinstance(current_spawn, dict)
                    and current_spawn.get("lease_id")
                    == lease_id
                ):
                    stem_job_status.pop(
                        f"spawn:{job_id}",
                        None,
                    )



@app.function(image=controller_image, secrets=[music_gen_secrets], timeout=120)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def separate_stems(request: dict):
    if request.get("action") == "status":
        job_id = request.get("remote_job_id")
        if not job_id:
            return {"status": "failed", "progress_pct": 0, "error_message": "Falta remote_job_id"}
        return _status(job_id) or {
            "status": "failed",
            "progress_pct": 0,
            "error_message": "Job remoto no encontrado o expirado",
        }

    s3_key = _validate_key(request.get("s3_key"))
    request = {**request, "s3_key": s3_key}
    if not request.get("async") and not ALLOW_SYNC:
        return {
            "status": "failed",
            "progress_pct": 0,
            "error_message": "La separación síncrona está deshabilitada; use async=true.",
        }
    if request.get("async"):
        job_id = _claim_job(request.get("client_job_id"))
        _spawn_if_needed(request, job_id)
        current = _status(job_id) or {"status": "failed", "progress_pct": 0}
        return {
            "remote_job_id": job_id,
            "status": current.get("status", "queued"),
            "progress_pct": current.get("progress_pct", 0),
        }

    # Keep the legacy synchronous contract for callers that can tolerate the
    # request duration. Django/Celery uses the async path to avoid HTTP timeouts.
    job_id = _claim_job(request.get("client_job_id"))
    _spawn_if_needed(request, job_id)
    while True:
        current = _status(job_id)
        if not current:
            return {"status": "failed", "progress_pct": 0, "error_message": "Job expirado"}
        if current.get("status") == "completed":
            return {"stems": current.get("stems", {})}
        if current.get("status") == "failed":
            return current
        time.sleep(1)
