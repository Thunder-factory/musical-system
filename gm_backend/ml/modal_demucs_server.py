"""CPU Demucs service exposed from the shared gm-music-server Modal app.

The controller endpoint does not load Demucs or a GPU. It only claims an
idempotent job and spawns the CPU worker class. The public request/response
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


controller_image = modal.Image.debian_slim().pip_install(
    "boto3",
    "pydantic",
)

demucs_image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg")
    .pip_install(
        "demucs>=4.0.0",
        "boto3",
        "torch",
        "torchaudio",
        "torchcodec",
    )
)

music_gen_secrets = modal.Secret.from_name("music-gen-secret")
stem_job_status = modal.Dict.from_name("gm-stem-job-status", create_if_missing=True)

JOB_TTL_SECONDS = int(os.environ.get("DEMUCS_JOB_TTL_SECONDS", "3600"))
SPAWN_LEASE_SECONDS = int(os.environ.get("DEMUCS_SPAWN_LEASE_SECONDS", "300"))
GPU_CONFIG = os.environ.get("DEMUCS_GPU", "T4")


def _now() -> int:
    return int(time.time())


def _get_r2_storage():
    required = (
        "R2_ACCOUNT_ID",
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
    current = stem_job_status.get(job_id, {})
    current.update(values)
    current["updated_at"] = _now()
    stem_job_status[job_id] = current


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
        if existing_id:
            return existing_id

    job_id = str(uuid.uuid4())
    lease_id = str(uuid.uuid4())
    claim = {
        "job_id": job_id,
        "state": "initializing",
        "created_at": _now(),
        "lease_id": lease_id,
        "expires_at": _now() + SPAWN_LEASE_SECONDS,
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


def _spawn_if_needed(request: dict, job_id: str):
    current = _ensure_job_status(job_id, request.get("client_job_id"))
    if current.get("status") in {"processing", "completed"}:
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
        # A worker that never reached `processing` left a stale lease.
        # Remove it before atomically claiming a new lease.
        stem_job_status.pop(spawn_key, None)

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
    def process(self, request: dict, job_id: str, lease_id: str | None = None):
        import demucs.separate
        import torch

        uploaded_keys: list[str] = []
        try:
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA no está disponible para Demucs.")
            device_name = torch.cuda.get_device_name(torch.cuda.current_device())
            # El controlador mantiene el lease hasta que el estado processing
            # quedó publicado. Así otra solicitud no puede lanzar un segundo
            # worker durante esa ventana.
            spawn_lease = stem_job_status.get(f"spawn:{job_id}")
            if lease_id and (
                not isinstance(spawn_lease, dict)
                or spawn_lease.get('lease_id') != lease_id
            ):
                return
            _set_status(job_id, status="processing", progress_pct=10)
            _set_status(job_id, device=device_name)
            stem_job_status.pop(f"spawn:{job_id}", None)
            r2_client, bucket_name = _get_r2_storage()

            with tempfile.TemporaryDirectory(prefix=f"demucs-{job_id}-") as work_dir:
                source_path = Path(work_dir) / "source"
                wav_path = Path(work_dir) / "input.wav"
                output_dir = Path(work_dir) / "output"
                r2_client.download_file(bucket_name, request["s3_key"], str(source_path))
                if source_path.stat().st_size <= 0:
                    raise ValueError("El objeto de audio está vacío.")

                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-i", str(source_path),
                     "-ar", "44100", "-ac", "2", str(wav_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                if not wav_path.exists() or wav_path.stat().st_size <= 0:
                    raise ValueError("FFmpeg no produjo un WAV válido.")

                _set_status(job_id, progress_pct=25)
                demucs.separate.main([
                    "--two-stems", "vocals",
                    "--device", "cuda",
                    "--out", str(output_dir),
                    str(wav_path),
                ])
                model_dir = output_dir / "htdemucs" / wav_path.stem
                result: dict[str, str] = {}
                for stem_type in ("vocals", "no_vocals"):
                    stem_path = model_dir / f"{stem_type}.wav"
                    if not stem_path.exists() or stem_path.stat().st_size <= 0:
                        raise ValueError(f"Demucs no produjo {stem_type}.wav válido.")
                    key = f"stems/{job_id}/{stem_type}.wav"
                    r2_client.upload_file(str(stem_path), bucket_name, key)
                    uploaded_keys.append(key)
                    result[stem_type] = key

                _set_status(
                    job_id,
                    status="completed",
                    progress_pct=100,
                    stems=result,
                    error_message=None,
                )
        except Exception as exc:
            try:
                r2_client, bucket_name = _get_r2_storage()
                for key in uploaded_keys:
                    r2_client.delete_object(Bucket=bucket_name, Key=key)
            except Exception:
                pass
            _set_status(
                job_id,
                status="failed",
                stems={},
                error_message=str(exc)[:500],
            )
            raise


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
