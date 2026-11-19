"""GPU FaceFusion service exposed from the shared gm-music-server Modal app.

Espejo de ``modal_demucs_server.py``: el endpoint ``face_swap`` corre en CPU, reclama
un job idempotente (``client_job_id``) y lanza la clase GPU ``FaceSwapServer``. Las
entradas y la salida viven en R2 (Secret ``music-gen-secret``); el estado se guarda en
el Dict ``gm-faceswap-job-status``. El único Volume es la cache de pesos de FaceFusion.

Pipeline portado de ``faceswap/worker/pipeline.py`` sin marca de agua: normalizar
(≤15 s, ≤720p, 25 FPS) → FaceFusion (swap + CodeFormer) → remux de audio a AAC.

Se despliega SOLO a través de ``modal deploy ml/modal_music_server.py``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable
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

faceswap_image = (
    modal.Image.from_registry("nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04", add_python="3.12")
    # curl: FaceFusion lo usa para descargar los modelos (sin él falla con "curl is not installed").
    .apt_install("ffmpeg", "git", "curl")
    # Mismas versiones que requirements.txt de FaceFusion 3.9.2, con onnxruntime-gpu para cuda@12.
    .pip_install(
        "gradio-rangeslider==0.0.8",
        "gradio==5.50.0",
        "numpy==2.5.4",
        "onnx==1.23.2",
        "onnxruntime-gpu==1.24.4",
        "opencv-python-headless==5.0.0.93",
        "tqdm==4.70.1",
        "scipy==1.18.1",
        "boto3",
    )
    .run_commands(
        "git clone --depth 1 --branch 3.9.2 "
        "https://github.com/facefusion/facefusion.git /facefusion",
        # La T4 (Turing) falla con cudnn_conv_algo_search=EXHAUSTIVE en CodeFormer ("Failed to
        # initialize CUDNN Frontend") y cae a CPU. FaceFusion ya usa DEFAULT para las GTX 16xx
        # (también Turing): sumamos la T4.
        "sed -i \"s/'GeForce GTX 1660')/'GeForce GTX 1660', 'Tesla T4')/\" "
        "/facefusion/facefusion/execution.py",
        "grep -q \"'Tesla T4'\" /facefusion/facefusion/execution.py",
    )
    .add_local_file(
        str(Path(__file__).with_name("modal_app.py")),
        remote_path="/root/modal_app.py",
    )
)

music_gen_secrets = modal.Secret.from_name("music-gen-secret")
faceswap_job_status = modal.Dict.from_name("gm-faceswap-job-status", create_if_missing=True)
# Pesos de FaceFusion: se bajan en la primera ejecución y quedan cacheados aquí.
faceswap_models = modal.Volume.from_name("gm-faceswap-models", create_if_missing=True)

FACEFUSION_DIR = "/facefusion"
TARGET_FPS = 25
MAX_SECONDS = 15
MAX_HEIGHT = 720
RESULT_PREFIX = "faceswap/results"
GPU_CONFIG = os.environ.get("FACESWAP_GPU", "T4")
JOB_TTL_SECONDS = int(os.environ.get("FACESWAP_JOB_TTL_SECONDS", "3600"))
SPAWN_LEASE_SECONDS = int(os.environ.get("FACESWAP_SPAWN_LEASE_SECONDS", "300"))
PROCESSING_STALE_SECONDS = int(os.environ.get("FACESWAP_PROCESSING_STALE_SECONDS", "1200"))
WORKER_LEASE_SECONDS = PROCESSING_STALE_SECONDS + 120
STATUS_UPDATE_LOCK_SECONDS = 30
STATUS_UPDATE_LOCK_WAIT_SECONDS = 2

PROGRESS_RE = re.compile(r"processing:\s*(\d+)%")
ProgressFn = Callable[[int], None]

DEFAULT_OPTS = {
    "swapper_model": "inswapper_128_fp16",
    "swapper_weight": 1.0,
    "enhancer_blend": 45,  # elegido en la comparación A/B/C del 2026-11-18 (B)
}


# --------------------------------------------------------------------------- #
# Helpers de estado y leases (copiados de modal_demucs_server.py).
# --------------------------------------------------------------------------- #


def _worker_owns_job(job_id: str, lease_id: str | None) -> bool:
    if not lease_id:
        return True
    lease = faceswap_job_status.get(f"worker:{job_id}")
    return isinstance(lease, dict) and lease.get("lease_id") == lease_id


def _worker_can_fail_job(job_id: str, lease_id: str | None) -> bool:
    """Allow the current spawn lease to publish pre-worker failures."""
    if _worker_owns_job(job_id, lease_id):
        return True
    spawn_lease = faceswap_job_status.get(f"spawn:{job_id}")
    return bool(
        lease_id
        and isinstance(spawn_lease, dict)
        and spawn_lease.get("lease_id") == lease_id
    )


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
        existing_lock = faceswap_job_status.get(lock_key)
        if isinstance(existing_lock, dict) and existing_lock.get("expires_at", 0) <= _now():
            reclaim_key = f"status-reclaim:{job_id}"
            if faceswap_job_status.put(
                reclaim_key,
                {"created_at": _now(), "expires_at": _now() + STATUS_UPDATE_LOCK_SECONDS},
                skip_if_exists=True,
            ):
                try:
                    latest_lock = faceswap_job_status.get(lock_key)
                    if (
                        isinstance(latest_lock, dict)
                        and latest_lock.get("expires_at", 0) <= _now()
                    ):
                        faceswap_job_status.pop(lock_key, None)
                finally:
                    faceswap_job_status.pop(reclaim_key, None)

        acquired = faceswap_job_status.put(
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
        current = faceswap_job_status.get(job_id, {})
        current.update(values)
        current["updated_at"] = _now()
        faceswap_job_status[job_id] = current
    finally:
        current_lock = faceswap_job_status.get(lock_key)
        if isinstance(current_lock, dict) and current_lock.get("lock_id") == lock_id:
            faceswap_job_status.pop(lock_key, None)


def _status(job_id: str):
    value = faceswap_job_status.get(job_id)
    if not value:
        return None
    if value.get("expires_at", 0) < _now():
        try:
            faceswap_job_status.pop(job_id, None)
            client_job_id = value.get("client_job_id")
            if client_job_id:
                faceswap_job_status.pop(f"client:{client_job_id}", None)
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


def _initial_status(client_job_id: str | None = None) -> dict:
    values = {
        "status": "queued",
        "progress_pct": 0,
        "output_s3_key": None,
        "error_message": None,
        "expires_at": _now() + JOB_TTL_SECONDS,
    }
    if client_job_id:
        values["client_job_id"] = client_job_id
    return values


def _claim_job(client_job_id: str | None) -> str:
    if not client_job_id:
        job_id = str(uuid.uuid4())
        faceswap_job_status[job_id] = _initial_status()
        return job_id

    client_key = f"client:{client_job_id}"
    existing = faceswap_job_status.get(client_key)
    if existing:
        existing_id = existing.get("job_id") if isinstance(existing, dict) else existing
        if existing_id and _status(existing_id):
            return existing_id

        recovery_key = f"client-recover:{client_job_id}"
        recovered = faceswap_job_status.put(
            recovery_key,
            {"created_at": _now(), "expires_at": _now() + SPAWN_LEASE_SECONDS},
            skip_if_exists=True,
        )
        if not recovered:
            latest = faceswap_job_status.get(client_key)
            latest_id = latest.get("job_id") if isinstance(latest, dict) else latest
            if latest_id and _status(latest_id):
                return latest_id
            raise RuntimeError("El client_job_id está siendo recuperado; reintente.")
        try:
            latest = faceswap_job_status.get(client_key)
            latest_id = latest.get("job_id") if isinstance(latest, dict) else latest
            if latest_id and _status(latest_id):
                return latest_id
            faceswap_job_status.pop(client_key, None)
        finally:
            faceswap_job_status.pop(recovery_key, None)

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
    claimed = faceswap_job_status.put(client_key, claim, skip_if_exists=True)
    if not claimed:
        existing = faceswap_job_status.get(client_key)
        existing_id = existing.get("job_id") if isinstance(existing, dict) else existing
        if existing_id:
            return existing_id
        raise RuntimeError("No se pudo reclamar el job de face swap.")

    faceswap_job_status[job_id] = _initial_status(client_job_id)
    return job_id


def _ensure_job_status(job_id: str, client_job_id: str | None):
    current = _status(job_id)
    if current:
        return current
    values = _initial_status(client_job_id)
    faceswap_job_status[job_id] = values
    return values


def _spawn_if_needed(request: dict, job_id: str, _recovery=False):
    current = _ensure_job_status(job_id, request.get("client_job_id"))
    recovery_key = f"recover:{job_id}"
    if current.get("status") == "processing":
        worker_lease = faceswap_job_status.get(f"worker:{job_id}")
        if isinstance(worker_lease, dict) and worker_lease.get("expires_at", 0) > _now():
            return current
        updated_at = current.get("updated_at", 0)
        if updated_at and updated_at + PROCESSING_STALE_SECONDS > _now():
            return current
        if not _recovery:
            claimed_recovery = faceswap_job_status.put(
                recovery_key,
                {"created_at": _now(), "expires_at": _now() + SPAWN_LEASE_SECONDS},
                skip_if_exists=True,
            )
            if not claimed_recovery:
                return current
            try:
                latest = _status(job_id)
                if latest and latest.get("status") == "processing":
                    _set_status(job_id, status="queued", retryable=True)
                    return _spawn_if_needed(request, job_id, _recovery=True)
            finally:
                faceswap_job_status.pop(recovery_key, None)
            return current
    if current.get("status") == "queued" and not _recovery:
        if faceswap_job_status.get(recovery_key):
            return current
    if current.get("status") == "completed":
        return current
    if current.get("status") == "failed" and not current.get("retryable"):
        return current

    spawn_key = f"spawn:{job_id}"
    existing_lease = faceswap_job_status.get(spawn_key)
    if existing_lease:
        lease_expires_at = (
            existing_lease.get("expires_at", 0) if isinstance(existing_lease, dict) else 0
        )
        if lease_expires_at > _now():
            return current
        # La comprobación y eliminación del lease vencido también necesitan
        # exclusión: dos controladores no deben borrar y reclamar el mismo
        # lease simultáneamente.
        reclaim_key = f"reclaim:{job_id}"
        reclaimed = faceswap_job_status.put(
            reclaim_key,
            {"created_at": _now(), "expires_at": _now() + SPAWN_LEASE_SECONDS},
            skip_if_exists=True,
        )
        if not reclaimed:
            return current
        try:
            latest_lease = faceswap_job_status.get(spawn_key)
            latest_expiry = (
                latest_lease.get("expires_at", 0) if isinstance(latest_lease, dict) else 0
            )
            if latest_expiry > _now():
                return current
            faceswap_job_status.pop(spawn_key, None)
        finally:
            faceswap_job_status.pop(reclaim_key, None)

    lease_id = str(uuid.uuid4())
    lease = {
        "created_at": _now(),
        "expires_at": _now() + SPAWN_LEASE_SECONDS,
        "lease_id": lease_id,
    }
    claimed = faceswap_job_status.put(spawn_key, lease, skip_if_exists=True)
    if claimed:
        try:
            faceswap_job_status[job_id] = {
                **current,
                "status": "queued",
                "error_message": None,
                "retryable": False,
                "expires_at": _now() + JOB_TTL_SECONDS,
            }
            FaceSwapServer().process.spawn(request, job_id, lease_id)
        except Exception as exc:
            faceswap_job_status.pop(spawn_key, None)
            _set_status(job_id, status="failed", retryable=True, error_message=str(exc)[:500])
            raise
    return _status(job_id) or current


# --------------------------------------------------------------------------- #
# Pipeline (portado de faceswap/worker/pipeline.py, sin marca de agua).
# --------------------------------------------------------------------------- #


def _run(cmd: list[str], cwd: str | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def _run_streaming(cmd: list[str], cwd: str, on_progress: ProgressFn | None) -> None:
    """Como _run, pero lee stdout+stderr en vivo: tqdm reescribe la línea con \\r, así que
    se separa por \\r y \\n, se reenvía al log y se parsea "processing: NN%"."""
    print("$", " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    buf, last = b"", -1
    while chunk := proc.stdout.read1(4096):
        buf += chunk
        *lines, buf = re.split(rb"[\r\n]", buf)
        for raw in lines:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            print(line, flush=True)
            match = PROGRESS_RE.search(line)
            if match and on_progress and int(match.group(1)) != last:
                last = int(match.group(1))
                on_progress(last)
    if buf.strip():
        print(buf.decode(errors="replace"), flush=True)
    if proc.wait() != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)


def normalize_video(src: Path, dst: Path) -> None:
    """Recorta a <=15 s, baja a <=720p y fija 25 FPS para acotar tiempo y costo."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", str(MAX_SECONDS),
        "-vf", f"scale=-2:'min({MAX_HEIGHT},ih)',fps={TARGET_FPS}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k", str(dst),
    ])


def _reference_frame_number(ref_time_s: float) -> int:
    """Fotograma del video normalizado (25 FPS) que corresponde al segundo elegido."""
    return round(ref_time_s * TARGET_FPS)


def _facefusion_command(
    photo: Path,
    video: Path,
    out: Path,
    ref_time_s: float | None,
    opts: dict | None = None,
    face_position: int | None = None,
) -> list[str]:
    """Arma el comando headless de FaceFusion (swap + CodeFormer).

    Con ``face_position`` (personaje elegido con un clic) usa el modo reference sobre el
    fotograma ``round(ref_time_s * 25)`` y la cara de esa posición en orden large-small.
    Con solo ref_time_s reemplaza la primera cara de ese segundo; sin él, la cara más
    grande de cada frame (clips propios).
    """
    opts = {**DEFAULT_OPTS, **(opts or {})}
    cmd = [
        "python", "facefusion.py", "headless-run",
        "--source-paths", str(photo), "--target-path", str(video), "--output-path", str(out),
        "--processors", "face_swapper", "face_enhancer",
        "--face-swapper-model", opts["swapper_model"],
        "--face-swapper-pixel-boost", "256x256",
        "--face-swapper-weight", str(opts["swapper_weight"]),
        "--face-enhancer-model", "codeformer",
        "--face-enhancer-blend", str(opts["enhancer_blend"]),
        "--execution-providers", "cuda",
        "--output-video-quality", "90",
        "--log-level", "info",
    ]
    if face_position is not None and ref_time_s is not None:
        cmd += [
            "--face-selector-mode", "reference",
            "--reference-frame-number", str(_reference_frame_number(ref_time_s)),
            "--face-selector-order", "large-small",
            "--reference-face-position", str(face_position),
        ]
    elif ref_time_s is not None and ref_time_s >= 0:
        cmd += [
            "--face-selector-mode", "reference",
            "--reference-frame-number", str(int(ref_time_s * TARGET_FPS)),
            "--reference-face-position", "0",
        ]
    else:
        cmd += ["--face-selector-mode", "one", "--face-selector-order", "large-small"]
    return cmd


def run_facefusion(
    photo: Path,
    video: Path,
    out: Path,
    ref_time_s: float | None,
    on_progress: ProgressFn | None = None,
    face_position: int | None = None,
) -> None:
    """Ejecuta FaceFusion y reporta su % de frames procesados (0-100)."""
    cmd = _facefusion_command(photo, video, out, ref_time_s, face_position=face_position)
    _run_streaming(cmd, FACEFUSION_DIR, on_progress)


# --------------------------------------------------------------------------- #
# Elegir el personaje: detectar caras con el mismo motor que FaceFusion.
# --------------------------------------------------------------------------- #

NO_FACE_AT_POINT = "No se encontró una cara en el punto elegido. Elige otro momento del video."
SELECTION_INCOMPLETE = "Para elegir el personaje envía ref_time_s, face_x y face_y juntos."
FACE_POINT_INVALID = "La posición de la cara debe estar entre 0 y 1."
# Si el clic no cae dentro de ninguna cara, se acepta la más cercana solo si su centro
# está a lo sumo a 1.5 veces el lado mayor de su bbox.
MAX_FACE_DISTANCE_FACTOR = 1.5
FACE_PROBE_PREFIX = "FACE_PROBE_JSON:"

# Corre con cwd=/facefusion. Inicializa el state_manager exactamente como
# facefusion/core.py:cli + process_step (create_program + apply_args con los MISMOS
# argumentos del headless-run) y replica la rama "reference" de
# facefusion/face_selector.py:select_faces: get_static_faces sobre el fotograma
# reference_frame_number y sort_and_filter_faces (orden large-small). Así el índice de
# la lista coincide con --reference-face-position.
FACE_PROBE_SCRIPT = """
import json, os, sys
os.environ['OMP_NUM_THREADS'] = '1'
sys.argv = ['facefusion.py', *json.loads(sys.argv[1])]
from facefusion import face_classifier, face_detector, face_landmarker, face_recognizer
from facefusion import logger, state_manager
from facefusion.args import apply_args
from facefusion.face_creator import get_static_faces
from facefusion.face_selector import sort_and_filter_faces
from facefusion.program import create_program
from facefusion.vision import read_static_images, read_static_video_frame

args = vars(create_program().parse_args())
apply_args(args, state_manager.init_item)
logger.init(state_manager.get_item('log_level'))
for module in (face_detector, face_landmarker, face_recognizer, face_classifier):
    if not module.pre_check():
        raise SystemExit('No se pudieron preparar los modelos de detección de caras.')
frame = read_static_video_frame(
    state_manager.get_item('target_path'), state_manager.get_item('reference_frame_number')
)
if frame is None:
    raise SystemExit('No se pudo leer el fotograma de referencia.')
source_faces = get_static_faces(read_static_images(state_manager.get_item('source_paths')))
faces = sort_and_filter_faces(source_faces, get_static_faces([frame]))
print(%r + json.dumps({
    'width': int(frame.shape[1]),
    'height': int(frame.shape[0]),
    'bboxes': [[float(v) for v in face.bounding_box[:4]] for face in faces],
}), flush=True)
""" % FACE_PROBE_PREFIX


def _map_point_to_frame(
    face_x: float, face_y: float, width: int, height: int
) -> tuple[float, float]:
    """Pasa el clic normalizado (sobre el fotograma original) a píxeles del normalizado.

    ``normalize_video`` solo escala proporcionalmente (``scale=-2:min(720,ih)``): no
    recorta, no rellena y la rotación de metadatos la aplica ffmpeg igual que el
    navegador. Por eso las proporciones se conservan y basta con multiplicar.
    """
    return face_x * width, face_y * height


def _choose_face_index(bboxes: list[list[float]], point: tuple[float, float]) -> int | None:
    """Índice (en el orden recibido) de la cara que contiene el punto o la más cercana.

    Si varias contienen el punto gana la de centro más cercano. Si ninguna lo contiene,
    la de centro más cercano siempre que esté a ≤ 1.5 × el lado mayor de su bbox.
    Devuelve None si no hay ninguna cara razonablemente cerca.
    """
    px, py = point
    best: tuple[bool, float, int] | None = None
    for index, (x1, y1, x2, y2) in enumerate(bboxes):
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        distance = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
        inside = x1 <= px <= x2 and y1 <= py <= y2
        if not inside and distance > MAX_FACE_DISTANCE_FACTOR * max(x2 - x1, y2 - y1):
            continue
        candidate = (not inside, distance, index)
        if best is None or candidate < best:
            best = candidate
    return None if best is None else best[2]


def _parse_probe_output(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        if line.startswith(FACE_PROBE_PREFIX):
            return json.loads(line[len(FACE_PROBE_PREFIX):])
    raise RuntimeError("No se pudieron detectar las caras del fotograma elegido.")


def detect_reference_faces(photo: Path, video: Path, ref_time_s: float) -> dict:
    """Bboxes en orden large-small de FaceFusion para el fotograma de referencia.

    Usa los mismos argumentos que el headless-run real (detector, score, orden...).
    """
    ff_args = _facefusion_command(
        photo, video, video.with_name("probe.mp4"), ref_time_s, face_position=0
    )[2:]
    cmd = ["python", "-c", FACE_PROBE_SCRIPT, json.dumps(ff_args)]
    print("$ python -c <face-probe>", " ".join(ff_args), flush=True)
    result = subprocess.run(cmd, cwd=FACEFUSION_DIR, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, flush=True)
    if result.returncode != 0:
        print(result.stderr, flush=True)
        raise RuntimeError("No se pudieron detectar las caras del fotograma elegido.")
    return _parse_probe_output(result.stdout)


def select_target_face(
    photo: Path, video: Path, ref_time_s: float, face_x: float, face_y: float
) -> int:
    """Devuelve el --reference-face-position de la cara que el usuario tocó."""
    probe = detect_reference_faces(photo, video, ref_time_s)
    point = _map_point_to_frame(face_x, face_y, probe["width"], probe["height"])
    index = _choose_face_index(probe["bboxes"], point)
    if index is None:
        raise ValueError(NO_FACE_AT_POINT)
    return index


def finalize_video(src: Path, dst: Path) -> None:
    """Remux sin recodificar el video; audio a AAC (FaceFusion deja FLAC y Safari/iOS no
    lo reproduce) y +faststart para que el <video> arranque antes de bajar todo."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(dst),
    ])


def _map_progress(facefusion_pct: int) -> int:
    """FaceFusion procesa los frames entre el 10 % y el 90 % del progreso del job."""
    return 10 + max(0, min(100, int(facefusion_pct))) * 80 // 100


def _validate_ref_time(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("ref_time_s no es válido.")
    if not 0 <= float(value) <= MAX_SECONDS:
        raise ValueError("ref_time_s no es válido.")
    return float(value)


def _validate_face_point(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(FACE_POINT_INVALID)
    if not 0 <= float(value) <= 1:
        raise ValueError(FACE_POINT_INVALID)
    return float(value)


def _validate_selection(request: dict) -> tuple[float | None, float | None, float | None]:
    """Valida ref_time_s y el clic opcional (face_x y face_y van juntos y con ref_time_s)."""
    ref_time_s = _validate_ref_time(request.get("ref_time_s"))
    face_x = _validate_face_point(request.get("face_x"))
    face_y = _validate_face_point(request.get("face_y"))
    if (face_x is None) != (face_y is None):
        raise ValueError(SELECTION_INCOMPLETE)
    if face_x is not None and ref_time_s is None:
        raise ValueError(SELECTION_INCOMPLETE)
    return ref_time_s, face_x, face_y


def _gpu_name() -> str:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip().splitlines()[0]
    except Exception:
        try:
            import onnxruntime

            return onnxruntime.get_device()
        except Exception:
            return "unknown"


# --------------------------------------------------------------------------- #
# Worker GPU y endpoint HTTP.
# --------------------------------------------------------------------------- #


@app.cls(
    image=faceswap_image,
    gpu=GPU_CONFIG,
    secrets=[music_gen_secrets],
    volumes={"/facefusion/.assets": faceswap_models},
    timeout=900,
    scaledown_window=120,
    max_containers=2,
)
class FaceSwapServer:

    @modal.method()
    def process(self, request: dict, job_id: str, lease_id: str | None = None):
        uploaded_keys: list[str] = []
        worker_lease_claimed = False
        worker_lease_id: str | None = None

        try:
            # Comprobar que el controlador sigue siendo propietario del lease de lanzamiento.
            spawn_lease = faceswap_job_status.get(f"spawn:{job_id}")
            if lease_id and (
                not isinstance(spawn_lease, dict) or spawn_lease.get("lease_id") != lease_id
            ):
                return

            worker_lease_id = lease_id or str(uuid.uuid4())
            # Impedir que dos workers procesen el mismo trabajo.
            worker_lease_claimed = faceswap_job_status.put(
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

            _set_status(job_id, status="processing", progress_pct=2, device=_gpu_name())
            faceswap_job_status.pop(f"spawn:{job_id}", None)

            r2_client, bucket_name = _get_r2_storage()
            photo_key = _validate_key(request["photo_s3_key"])
            video_key = _validate_key(request["video_s3_key"])
            ref_time_s, face_x, face_y = _validate_selection(request)
            timings: dict[str, float] = {}

            with tempfile.TemporaryDirectory(prefix=f"faceswap-{job_id}-") as work_dir:
                work = Path(work_dir)
                photo_path = work / f"source{Path(photo_key).suffix.lower() or '.jpg'}"
                target_path = work / f"target{Path(video_key).suffix.lower() or '.mp4'}"
                norm, swapped, final = work / "norm.mp4", work / "swapped.mp4", work / "final.mp4"

                r2_client.download_file(bucket_name, photo_key, str(photo_path))
                r2_client.download_file(bucket_name, video_key, str(target_path))
                if photo_path.stat().st_size <= 0 or target_path.stat().st_size <= 0:
                    raise ValueError("La foto o el video de entrada están vacíos.")
                _set_status(job_id, progress_pct=5)

                started = time.perf_counter()
                normalize_video(target_path, norm)
                timings["normalize"] = round(time.perf_counter() - started, 1)
                _set_status(job_id, progress_pct=10)

                face_position = None
                if face_x is not None:
                    started = time.perf_counter()
                    face_position = select_target_face(
                        photo_path, norm, ref_time_s, face_x, face_y
                    )
                    timings["face_select"] = round(time.perf_counter() - started, 1)

                sent = {"pct": 10}

                def report(facefusion_pct: int) -> None:
                    pct = _map_progress(facefusion_pct)
                    if pct - sent["pct"] >= 5:  # como mucho cada 5 puntos
                        sent["pct"] = pct
                        _set_status(job_id, progress_pct=pct)

                started = time.perf_counter()
                run_facefusion(photo_path, norm, swapped, ref_time_s, report, face_position)
                timings["facefusion"] = round(time.perf_counter() - started, 1)
                if not swapped.exists():
                    raise RuntimeError("No se detectó una cara en la foto o en el video.")

                started = time.perf_counter()
                finalize_video(swapped, final)
                timings["remux"] = round(time.perf_counter() - started, 1)
                _set_status(job_id, progress_pct=95)

                output_key = f"{RESULT_PREFIX}/{job_id}.mp4"
                r2_client.upload_file(
                    str(final), bucket_name, output_key, ExtraArgs={"ContentType": "video/mp4"}
                )
                uploaded_keys.append(output_key)

            # Guarda los pesos que FaceFusion haya descargado para los próximos arranques.
            faceswap_models.commit()

            # Impedir que un worker antiguo publique resultados si perdió su lease.
            if not _worker_owns_job(job_id, worker_lease_id):
                for key in uploaded_keys:
                    r2_client.delete_object(Bucket=bucket_name, Key=key)
                return

            _set_status(
                job_id,
                status="completed",
                progress_pct=100,
                output_s3_key=output_key,
                error_message=None,
                timings=timings,
            )

        except Exception as exc:
            # Determinar propiedad antes de liberar el lease.
            if _worker_can_fail_job(job_id, worker_lease_id):
                try:
                    r2_client, bucket_name = _get_r2_storage()
                    for key in uploaded_keys:
                        r2_client.delete_object(Bucket=bucket_name, Key=key)
                except Exception:
                    pass
                _set_status(
                    job_id,
                    status="failed",
                    progress_pct=0,
                    output_s3_key=None,
                    error_message=str(exc)[:500],
                )
            raise

        finally:
            # Liberar únicamente los leases que pertenecen a esta ejecución.
            if worker_lease_claimed:
                current_worker = faceswap_job_status.get(f"worker:{job_id}")
                if (
                    isinstance(current_worker, dict)
                    and current_worker.get("lease_id") == worker_lease_id
                ):
                    faceswap_job_status.pop(f"worker:{job_id}", None)
            if lease_id:
                current_spawn = faceswap_job_status.get(f"spawn:{job_id}")
                if isinstance(current_spawn, dict) and current_spawn.get("lease_id") == lease_id:
                    faceswap_job_status.pop(f"spawn:{job_id}", None)


def _failed(message: str) -> dict:
    return {"status": "failed", "progress_pct": 0, "error_message": message}


@app.function(image=controller_image, secrets=[music_gen_secrets], timeout=120)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def face_swap(request: dict):
    if request.get("action") == "status":
        job_id = request.get("remote_job_id")
        if not job_id:
            return _failed("Falta remote_job_id")
        return _status(job_id) or _failed("Job remoto no encontrado o expirado")

    try:
        photo_key = _validate_key(request.get("photo_s3_key"))
        video_key = _validate_key(request.get("video_s3_key"))
        ref_time_s, face_x, face_y = _validate_selection(request)
    except ValueError as exc:
        return _failed(str(exc))
    if not request.get("async"):
        return _failed("La ejecución síncrona está deshabilitada; use async=true.")

    request = {
        **request,
        "photo_s3_key": photo_key,
        "video_s3_key": video_key,
        "ref_time_s": ref_time_s,
        "face_x": face_x,
        "face_y": face_y,
    }
    job_id = _claim_job(request.get("client_job_id"))
    _spawn_if_needed(request, job_id)
    current = _status(job_id) or {"status": "failed", "progress_pct": 0}
    return {
        "remote_job_id": job_id,
        "status": current.get("status", "queued"),
        "progress_pct": current.get("progress_pct", 0),
    }
