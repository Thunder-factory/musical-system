"""Servicio de traducción (doblaje) de videos musicales en Modal.

App independiente de gm-music-server, para desplegarla sin tocar la generación
musical ni la separación de stems:

    modal deploy ml/modal_translation_server.py

Contrato (POST con proxy auth, igual que separate_stems):
  - Crear:   {"s3_key", "client_job_id", "target_language", "title"?, "artist"?, "async": true}
             → {"remote_job_id", "status", "stage", "progress_pct"}
  - Estado:  {"action": "status", "remote_job_id"}
             → {"status", "stage", "progress_pct", "mode", "outputs", "details", "error_message"}

Dos workers con el mismo contrato; Django elige con "mode" (TRANSLATION_MODE):
  - real:      pipeline de SW1 (ml/translation_worker) en GPU: Demucs → Whisper
               (+ LRCLIB) → Gemini → XTTS-v2 → igualar voz → mezcla y remux.
  - simulated: solo CPU, sin modelos. Recorre las mismas etapas y sube archivos
               de prueba con el formato definitivo. Sirve para probar sin gastar GPU.

Ambos suben a R2: translations/<job>/resultado.mp4, voz.mp3 y letra.json.

Antes del primer trabajo real conviene descargar los modelos al volumen (CPU, sin GPU):

    modal run ml/modal_translation_server.py::prepare_translation_models
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import modal

app = modal.App("gm-translation-server")

controller_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "fastapi[standard]",
    "boto3",
)
simulated_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install("boto3")
)

WORKER_DIR = Path(__file__).resolve().parent / "translation_worker"
SITE_PACKAGES = "/usr/local/lib/python3.12/site-packages"
SEEDVC_DIR = "/opt/seed-vc"
SEEDVC_COMMIT = "51383ef"
RMVPE_PATH = "/models/applio/rvc/models/predictors/rmvpe.pt"
SEPARATOR_VENV = "/opt/separator"
ROFORMER_MODEL = "vocals_mel_band_roformer.ckpt"
DEREVERB_MODEL = "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt"

# Pipeline real (SW1). torch 2.5.1: desde 2.6 torch.load rompe la carga de Demucs 4.0.1.
real_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install("torch==2.5.1", "torchaudio==2.5.1", index_url="https://download.pytorch.org/whl/cu124")
    .pip_install(
        "demucs==4.0.1",
        "faster-whisper>=1.1,<2",
        "coqui-tts>=0.25,<0.28",
        "transformers>=4.57,<5",
        "six>=1.16",
        "pypinyin>=0.50",
        "pydantic>=2.7",
        "pydantic-settings>=2.3",
        "httpx>=0.27",
        "nvidia-ml-py>=12.560",
        "soundfile>=0.12",
        "scipy",
        "boto3",
    )
    # Seed-VC (canto): misma versión que usaba SW1. Sus checkpoints viven en el volumen.
    .apt_install("git")
    .pip_install(
        "librosa>=0.10",
        "munch>=4",
        "einops>=0.8",
        "pyyaml",
        "matplotlib",
        "onnxruntime",
        "huggingface-hub",
        "tqdm",
    )
    .run_commands(
        f"git clone https://github.com/Plachtaa/seed-vc.git {SEEDVC_DIR}",
        f"cd {SEEDVC_DIR} && git checkout {SEEDVC_COMMIT}",
        f"rm -rf {SEEDVC_DIR}/checkpoints && ln -s /models/seedvc/checkpoints {SEEDVC_DIR}/checkpoints",
    )
    # Separación MelBand RoFormer + de-reverb (audio-separator) en un entorno aparte, como en SW1:
    # sus dependencias no se mezclan con torch 2.5.1 / coqui-tts del worker.
    .run_commands(
        f"python -m venv {SEPARATOR_VENV}",
        # [cpu] trae onnxruntime, que audio-separator importa siempre; RoFormer corre en GPU vía torch.
        # audioread y pkg_resources (setuptools) los importa pero no los declara (librosa 0.11 ya no
        # trae audioread).
        # torch fijado a CUDA 12.4 (como el worker): el de PyPI trae CUDA 13, que puede no ser compatible
        # con el controlador de la GPU y haría que RoFormer corriera en CPU.
        "printf 'torch==2.5.1+cu124\\ntorchvision==0.20.1+cu124\\ntorchaudio==2.5.1+cu124\\n' > /tmp/torch-cu124.txt",
        f"{SEPARATOR_VENV}/bin/pip install --no-cache-dir -c /tmp/torch-cu124.txt "
        "--extra-index-url https://download.pytorch.org/whl/cu124 "
        "torch torchvision torchaudio 'audio-separator[cpu]==0.48.0' audioread 'setuptools<81'",
        # Si falta alguna dependencia, el deploy falla aquí y no en mitad de un trabajo.
        f"{SEPARATOR_VENV}/bin/python -c 'import torch; from audio_separator.separator import Separator; "
        "print(\"audio-separator OK, torch\", torch.__version__)'",
    )
    # Métricas de evaluación: parecido de voz (Resemblyzer).
    .pip_install("webrtcvad-wheels")
    .run_commands("pip install --no-cache-dir --no-deps resemblyzer")
    .env({
        # ctranslate2 (faster-whisper) usa el cuDNN 9 / cuBLAS que instala torch.
        "LD_LIBRARY_PATH": f"{SITE_PACKAGES}/nvidia/cudnn/lib:{SITE_PACKAGES}/nvidia/cublas/lib",
        "PYTHONPATH": "/root/worker",
        # Configuración del pipeline de SW1 (app/config.py lee estas variables).
        "DIR_MODELOS": "/models",
        "DIR_TRABAJO": "/tmp/work",
        "DISPOSITIVO": "cuda",
        "VRAM_LIMITE_MB": "22000",
        # Separación más limpia que Demucs (menos restos de la voz original = menos eco) y voz sin
        # reverb como referencia de timbre y melodía.
        "SEPARADOR": "roformer",
        "ROFORMER_PYTHON": f"{SEPARATOR_VENV}/bin/python",
        "ROFORMER_MODELO": ROFORMER_MODEL,
        "ROFORMER_DEREVERB": DEREVERB_MODEL,
        # Menos reverb añadida: la voz ya se mezcla con el carácter de la original.
        "IGUALAR_REVERB_MEZCLA": "0.12",
        # Ritmo: traducciones más cortas y menos aceleración por frase.
        "SILABAS_POR_SEGUNDO": "4.5",
        "REINTENTOS_SILABAS": "3",
        "TEMPO_MAX": "1.4",
        "WHISPER_MODELO": "large-v3",
        "WHISPER_COMPUTE": "float16",
        "LLM_PROVEEDOR": "gemini",
        "COQUI_TOS_AGREED": "1",  # XTTS-v2: licencia CPML, uso no comercial (proyecto académico)
        "IDIOMAS_SOPORTADOS": "en,es,fr,zh",
        "MAX_DURACION_S": "305",
        "MAX_TAMANO_MB": "300",
        # Canto (Seed-VC): la voz de XTTS se convierte al timbre del cantante con SU melodía.
        # Se puede desactivar por trabajo con "sing": false (TRANSLATION_SING en Django).
        "CANTO_ACTIVO": "true",
        "SEEDVC_DIR": SEEDVC_DIR,
        "RVC_APPLIO": "/models/applio",  # solo para la ruta de rmvpe.pt (extractor de melodía)
        "CANTO_MELODIA": "original",
        "CANTO_PASOS": "50",            # máximo recomendado por Seed-VC: menos sonido robótico
        "CANTO_REFERENCIA_S": "20",     # más segundos de la voz original = timbre más parecido
        "CANTO_LIMPIAR": "true",        # melodía sin saltos de octava ni picos: menos «gallos»
        "RVC_ACTIVO": "false",
    })
    .add_local_dir(str(WORKER_DIR), remote_path="/root/worker")
)

secrets = [modal.Secret.from_name("music-gen-secret")]
translation_secrets = [*secrets, modal.Secret.from_name("translation-secret")]
models_volume = modal.Volume.from_name("gm-translation-models", create_if_missing=True)
job_status = modal.Dict.from_name("gm-translation-job-status", create_if_missing=True)

MODES = {"real", "simulated"}
MODE = "simulated"  # modo del worker simulado (se informa en el estado)
SUPPORTED_LANGUAGES = {"en", "es", "fr", "zh"}
JOB_TTL_SECONDS = 6 * 3600
MAX_DURATION_SECONDS = 300 + 5  # margen por redondeo de contenedores
SIMULATED_SECONDS = 24

# Etapas del pipeline de SW1: (nombre, progreso al entrar, fracción del tiempo simulado).
STAGES = [
    ("extrayendo", 10, 0.05),
    ("separando", 25, 0.15),
    ("transcribiendo", 40, 0.20),
    ("traduciendo", 55, 0.25),
    ("sintetizando", 80, 0.25),
    ("mezclando", 92, 0.10),
]

# Letra de demostración (mismo formato que letra.json real): (inicio, fin, {idioma: verso}).
_DEMO_VERSES = [
    (0.5, 2.0, {"en": "The lights come up tonight", "es": "Se encienden luces hoy",
                "fr": "Les lumières s'allument", "zh": "今夜灯光亮起"}),
    (2.2, 3.8, {"en": "I hear the city sing", "es": "Oigo cantar la ciudad",
                "fr": "J'entends chanter la ville", "zh": "我听见城市歌唱"}),
    (4.0, 5.6, {"en": "Hold on, we're almost there", "es": "Aguanta, ya casi es",
                "fr": "Tiens bon, on y est presque", "zh": "坚持住，快到了"}),
    (5.8, 7.4, {"en": "One voice, a thousand ways", "es": "Una voz, mil caminos",
                "fr": "Une voix, mille chemins", "zh": "一个声音，千条路"}),
    (7.6, 9.5, {"en": "This song belongs to you", "es": "Esta canción es de ti",
                "fr": "Cette chanson est à toi", "zh": "这首歌属于你"}),
]


# ─── Utilidades ──────────────────────────────────────────────────────────────

def _now() -> int:
    return int(time.time())


def _r2():
    import boto3

    required = ("R2_ENDPOINT", "R2_REGION", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_DOCUMENTS_BUCKET")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Faltan variables R2 en el secreto de Modal: " + ", ".join(missing))
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        region_name=os.environ["R2_REGION"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    return client, os.environ["R2_DOCUMENTS_BUCKET"]


def _status(job_id: str) -> dict | None:
    value = job_status.get(job_id)
    if not isinstance(value, dict):
        return None
    if value.get("expires_at", 0) < _now():
        job_status.pop(job_id, None)
        return None
    return value


def _set_status(job_id: str, **values) -> None:
    """Solo el worker de cada trabajo escribe su estado tras crearlo; no hay carreras."""
    current = job_status.get(job_id) or {}
    current.update(values)
    current["updated_at"] = _now()
    job_status[job_id] = current


def _public_status(job_id: str, current: dict) -> dict:
    return {
        "remote_job_id": job_id,
        "status": current.get("status", "failed"),
        "stage": current.get("stage", ""),
        "progress_pct": current.get("progress_pct", 0),
        "mode": current.get("mode", MODE),
        "outputs": current.get("outputs", {}),
        "details": current.get("details", {}),
        "error_message": current.get("error_message"),
    }


def _validate_request(request: dict) -> dict:
    s3_key = request.get("s3_key")
    if not isinstance(s3_key, str) or not s3_key.strip():
        raise ValueError("s3_key es obligatorio.")
    s3_key = s3_key.strip()
    if s3_key.startswith("/") or ".." in Path(s3_key).parts:
        raise ValueError("s3_key no es válido.")

    language = str(request.get("target_language") or "").strip().lower()
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Idioma no soportado: {language or '(vacío)'}.")

    def _text(name: str) -> str | None:
        value = request.get(name)
        return str(value).strip()[:200] if value else None

    mode = str(request.get("mode") or "real").strip().lower()
    if mode not in MODES:
        raise ValueError(f"Modo no válido: {mode}.")

    return {
        "s3_key": s3_key,
        "target_language": language,
        "client_job_id": str(request.get("client_job_id") or uuid.uuid4()),
        "title": _text("title"),
        "artist": _text("artist"),
        "mode": mode,
        "sing": str(request.get("sing", True)).strip().lower() not in {"false", "0", "no"},
        # depuración: conservar y subir a R2 los archivos intermedios (por defecto no)
        "debug": str(request.get("debug", False)).strip().lower() in {"true", "1", "yes", "si", "sí"},
    }


def _probe(path: Path) -> tuple[float, bool]:
    """Devuelve (duración en segundos, tiene_audio)."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    info = json.loads(result.stdout or "{}")
    duration = float(info.get("format", {}).get("duration") or 0)
    has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    return duration, has_audio


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True, text=True)


def _demo_lyrics(target: str, title: str | None, artist: str | None) -> dict:
    source = "es" if target == "en" else "en"
    lyrics = {
        "idioma_origen": source,
        "idioma_destino": target,
        "modelo": "simulado",
        "fuente_letra": "lrclib" if title else "whisper",
        "resumen": "Datos de prueba del modo simulado: no es la letra del video enviado.",
        "frases": [
            {"inicio": start, "fin": end, "original": verse[source], "texto": verse[target]}
            for start, end, verse in _DEMO_VERSES
        ],
    }
    if title:
        lyrics["titulo"] = title
    if artist:
        lyrics["artista"] = artist
    return lyrics


# ─── Worker simulado (CPU) ───────────────────────────────────────────────────

@app.function(image=simulated_image, secrets=secrets, cpu=1.0, timeout=900)
def run_simulated_translation(params: dict, job_id: str) -> None:
    uploaded: list[str] = []
    client = bucket = None
    try:
        client, bucket = _r2()
        _set_status(job_id, status="processing", stage="descargando", progress_pct=5)

        with tempfile.TemporaryDirectory(prefix=f"translation-{job_id}-") as work:
            work_dir = Path(work)
            source = work_dir / ("source" + Path(params["s3_key"]).suffix.lower())
            client.download_file(bucket, params["s3_key"], str(source))

            duration, has_audio = _probe(source)
            if not has_audio:
                raise ValueError("El video no tiene pista de audio.")
            if duration <= 0 or duration > MAX_DURATION_SECONDS:
                raise ValueError("La duración del video no es válida (máximo 5 minutos).")

            for stage, progress, share in STAGES:
                _set_status(job_id, stage=stage, progress_pct=progress)
                time.sleep(SIMULATED_SECONDS * share)

            # resultado.mp4: el mismo video en MP4 (el modo real cambiará la voz).
            result_video = work_dir / "resultado.mp4"
            try:
                _ffmpeg("-i", str(source), "-map", "0:v:0", "-map", "0:a:0", "-c", "copy",
                        "-movflags", "+faststart", str(result_video))
            except subprocess.CalledProcessError:
                _ffmpeg("-i", str(source), "-map", "0:v:0", "-map", "0:a:0",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(result_video))

            # voz.mp3: un tono de prueba en lugar de la voz sintetizada.
            voice = work_dir / "voz.mp3"
            _ffmpeg("-f", "lavfi", "-i", f"sine=frequency=440:duration={min(duration, 10):.2f}",
                    "-q:a", "6", str(voice))

            lyrics_path = work_dir / "letra.json"
            lyrics = _demo_lyrics(params["target_language"], params["title"], params["artist"])
            lyrics_path.write_text(json.dumps(lyrics, ensure_ascii=False, indent=2), encoding="utf-8")

            _set_status(job_id, stage="subiendo", progress_pct=98)
            outputs = {}
            for name, path, content_type in (
                ("video", result_video, "video/mp4"),
                ("audio", voice, "audio/mpeg"),
                ("lyrics", lyrics_path, "application/json"),
            ):
                key = f"translations/{job_id}/{path.name}"
                client.upload_file(str(path), bucket, key, ExtraArgs={"ContentType": content_type})
                uploaded.append(key)
                outputs[name] = key

        _set_status(
            job_id,
            status="completed",
            stage="completado",
            progress_pct=100,
            outputs=outputs,
            error_message=None,
            details={
                "mode": MODE,
                "modelo_llm": "simulado",
                "fuente_letra": lyrics["fuente_letra"],
                "duracion_s": round(duration, 2),
                "nota": "Modo simulado: el video conserva su audio original y la voz es un tono de prueba.",
            },
        )
    except Exception as exc:
        if client is not None:
            for key in uploaded:
                try:
                    client.delete_object(Bucket=bucket, Key=key)
                except Exception:
                    pass
        _set_status(job_id, status="failed", outputs={}, error_message=str(exc)[:500])
        raise


# ─── Worker real (GPU): pipeline de SW1 ──────────────────────────────────────

# Archivos intermedios que se suben en modo depuración: (ruta dentro de la carpeta del trabajo, nombre en R2).
# Los WAV se suben como FLAC (sin pérdida, ~la mitad de tamaño).
DEBUG_FILES = [
    ("audio.wav", "01_audio_original.flac"),
    ("stems/voz.wav", "02_voz_separada.flac"),
    ("stems/voz_seca.wav", "03_voz_sin_reverb.flac"),
    ("stems/instrumental.wav", "04_instrumental.flac"),
    ("whisper_diagnostico.json", "05_whisper_diagnostico.json"),
    ("letra_original.json", "06_letra_original.json"),
    ("letra.json", "07_letra_traducida.json"),
    ("frases/informe_versos.json", "08_informe_versos.json"),
    ("voz_nueva.wav", "09_voz_xtts.flac"),
    ("voz_cantada.wav", "10_voz_seedvc.flac"),
    ("voz_rvc.wav", "11_voz_rvc.flac"),
    ("voz_igualada.wav", "12_voz_igualada.flac"),
    ("voz_completa.wav", "12b_voz_con_relleno_original.flac"),
    ("mezcla.wav", "13_mezcla_final.flac"),
    ("validacion.json", "15_validacion.json"),
]


def _upload_debug(client, bucket: str, job_id: str, work: Path, log_path: Path | None) -> dict:
    """Modo depuración: sube a R2 los intermedios que existan en `work` y el log del pipeline.

    Nunca lanza error (la depuración no debe hacer fallar un trabajo). Devuelve {prefijo, archivos, errores}.
    """
    import shutil
    import zipfile

    import soundfile as sf

    prefix = f"translations/{job_id}/debug/"
    subidos, errores = [], []

    def subir(path: Path, name: str, content_type: str) -> None:
        try:
            client.upload_file(str(path), bucket, prefix + name, ExtraArgs={"ContentType": content_type})
            subidos.append(name)
        except Exception as exc:  # noqa: BLE001
            errores.append(f"{name}: {exc}"[:200])

    with tempfile.TemporaryDirectory(prefix="debug-") as tmp:
        for rel, name in DEBUG_FILES:
            path = work / rel
            if not path.is_file():
                continue
            if name.endswith(".flac"):
                try:
                    data, sr = sf.read(str(path), dtype="int16", always_2d=True)
                    flac = Path(tmp) / name
                    sf.write(str(flac), data, sr, format="FLAC", subtype="PCM_16")
                    subir(flac, name, "audio/flac")
                except Exception as exc:  # noqa: BLE001
                    errores.append(f"{name}: {exc}"[:200])
            else:
                subir(path, name, "application/json")
        frases = work / "frases"
        if frases.is_dir():  # cada verso de XTTS antes (_crudo) y después de ajustar su duración
            paquete = Path(tmp) / "14_versos_xtts.zip"
            with zipfile.ZipFile(paquete, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in sorted(frases.glob("*.wav")):
                    zf.write(f, f.name)
            subir(paquete, paquete.name, "application/zip")
        if log_path and log_path.is_file():
            subir(log_path, "00_pipeline.log", "text/plain; charset=utf-8")
    shutil.rmtree(work, ignore_errors=True)
    print(f"depuración: {len(subidos)} archivos en {prefix}" + (f" ({len(errores)} errores)" if errores else ""))
    return {"prefijo": prefix, "archivos": subidos, **({"errores": errores} if errores else {})}


def _friendly_error(exc: Exception) -> str:
    """Mensaje para el usuario; los errores de entrada de SW1 ya vienen redactados."""
    try:
        from app.errores import EntradaInvalida
    except ImportError:  # pragma: no cover - solo dentro de la imagen real
        EntradaInvalida = ()  # noqa: N806
    if EntradaInvalida and isinstance(exc, EntradaInvalida):
        return f"El video no es válido: {exc}"
    return f"Error en el doblaje: {exc}"


@app.function(
    image=real_image,
    gpu="A10G",
    cpu=4.0,
    memory=16384,
    secrets=translation_secrets,
    volumes={"/models": models_volume},
    timeout=2400,
    scaledown_window=60,
)
def run_real_translation(params: dict, job_id: str) -> None:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    uploaded: list[str] = []
    client = bucket = None
    debug = bool(params.get("debug"))
    debug_info: dict = {}
    debug_work: Path | None = None
    log_handler = None
    log_path = Path(tempfile.gettempdir()) / f"pipeline-{job_id}.log"
    if debug:  # el log completo del pipeline también se guarda
        log_handler = logging.FileHandler(log_path, encoding="utf-8")
        log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(log_handler)
    try:
        from app.config import Config
        from app.pipeline.ejecutar import ejecutar_pipeline

        client, bucket = _r2()
        _set_status(job_id, status="processing", stage="descargando", progress_pct=5, mode="real")

        with tempfile.TemporaryDirectory(prefix=f"translation-{job_id}-") as work:
            work_dir = Path(work)
            source = work_dir / ("source" + Path(params["s3_key"]).suffix.lower())
            client.download_file(bucket, params["s3_key"], str(source))

            started = time.time()
            sing = bool(params.get("sing", True))
            cfg = Config(canto_activo=sing)
            if debug:  # ejecutar_pipeline trabaja en DIR_TRABAJO/<job_id[:12]>; ahí quedan los intermedios
                debug_work = cfg.ruta_trabajo / job_id[:12]
            result = ejecutar_pipeline(
                source,
                params["target_language"],
                work_dir / "salida",
                cfg,
                job_id=job_id[:12],
                al_progreso=lambda stage, progress: _set_status(job_id, stage=stage, progress_pct=progress),
                conservar_temporales=debug,
                titulo=params.get("title"),
                artista=params.get("artist"),
            )
            elapsed = round(time.time() - started, 1)
            if debug and debug_work is not None:
                _set_status(job_id, stage="subiendo", progress_pct=96)
                log_handler.flush()
                debug_info = _upload_debug(client, bucket, job_id, debug_work, log_path)

            _set_status(job_id, stage="subiendo", progress_pct=98)
            outputs = {}
            for name, path, content_type in (
                ("video", result["video"], "video/mp4"),
                ("audio", result["audio"], "audio/mpeg"),
                ("lyrics", result["letra"], "application/json"),
            ):
                key = f"translations/{job_id}/{Path(path).name}"
                client.upload_file(str(path), bucket, key, ExtraArgs={"ContentType": content_type})
                uploaded.append(key)
                outputs[name] = key

        _set_status(
            job_id,
            status="completed",
            stage="completado",
            progress_pct=100,
            outputs=outputs,
            error_message=None,
            details={
                "mode": "real",
                "canto": sing,
                "modelo_llm": result.get("modelo_llm"),
                "motivo_nivel_llm": result.get("motivo_nivel_llm"),
                "fuente_letra": result.get("fuente_letra"),
                "duracion_s": result.get("duracion_s"),
                "segundos_proceso": elapsed,
                "etapas": [
                    {k: m.get(k) for k in ("etapa", "segundos", "vram_pico_mb") if k in m}
                    for m in result.get("medidas", [])
                ],
                # MusicAI: secciones de la canción que desaparecieron (None si no se validó)
                **({"validacion": result["validacion"]} if result.get("validacion") else {}),
                **({"debug": debug_info} if debug_info else {}),
            },
        )
    except Exception as exc:
        if client is not None:
            for key in uploaded:
                try:
                    client.delete_object(Bucket=bucket, Key=key)
                except Exception:
                    pass
        # en depuración, los intermedios de un trabajo fallido son justo los que más interesan
        if debug and client is not None and debug_work is not None and debug_work.exists() and not debug_info:
            if log_handler:
                log_handler.flush()
            debug_info = _upload_debug(client, bucket, job_id, debug_work, log_path)
        _set_status(job_id, status="failed", outputs={}, error_message=_friendly_error(exc)[:500],
                    **({"details": {"mode": "real", "debug": debug_info}} if debug_info else {}))
        raise
    finally:
        if log_handler:
            logging.getLogger().removeHandler(log_handler)
            log_handler.close()
        try:
            models_volume.commit()  # los modelos descargados quedan para el próximo trabajo
        except Exception:
            pass


@app.function(
    image=real_image,
    secrets=translation_secrets,
    volumes={"/models": models_volume},
    timeout=3600,
)
def prepare_translation_models() -> None:
    """Descarga Demucs, Whisper large-v3, XTTS-v2 y Seed-VC al volumen una sola vez (sin GPU).

    Es idempotente: lo que ya está en el volumen no se vuelve a descargar.
    """
    import subprocess
    import sys

    from app.config import Config, preparar_entorno_modelos

    cfg = Config()
    preparar_entorno_modelos(cfg)

    from demucs.pretrained import get_model
    get_model(cfg.demucs_modelo)
    print(f"Demucs {cfg.demucs_modelo}: listo")

    from faster_whisper import download_model
    print(f"Whisper {cfg.whisper_modelo}: listo en {download_model(cfg.whisper_modelo)}")

    from TTS.utils.manage import ModelManager
    print(f"XTTS-v2: listo en {ModelManager(progress_bar=False).download_model(cfg.xtts_modelo)[0]}")

    # Seed-VC: mismas rutas de caché que usará cantar.py (que luego trabaja sin conexión).
    Path("/models/seedvc/checkpoints").mkdir(parents=True, exist_ok=True)
    hf_home = cfg.ruta_modelos / "huggingface"
    env = {**os.environ, "HF_HOME": str(hf_home), "HF_HUB_CACHE": str(hf_home / "hub"),
           "PYTHONIOENCODING": "utf-8"}
    env.pop("HF_HUB_OFFLINE", None)
    subprocess.run(
        [sys.executable, "/root/worker/scripts/externos/seedvc_preparar.py", "--rmvpe", RMVPE_PATH],
        cwd=SEEDVC_DIR, env=env, check=True,
    )

    # RoFormer (voz/instrumental) y de-reverb, en el entorno de audio-separator.
    separation_dir = cfg.ruta_modelos / "separacion"
    separation_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [f"{SEPARATOR_VENV}/bin/python", "-c",
         "import sys, logging; from audio_separator.separator import Separator; "
         "s = Separator(log_level=logging.WARNING, model_file_dir=sys.argv[1]); "
         "[s.load_model(model_filename=m) or print('listo:', m) for m in sys.argv[2:]]",
         str(separation_dir), ROFORMER_MODEL, DEREVERB_MODEL],
        check=True,
    )

    models_volume.commit()


# ─── Evaluación (métricas para comparar versiones) ───────────────────────────

def _pitch_jumps(f0, frames_per_second: float = 100.0) -> dict:
    """Saltos bruscos de tono en la voz nueva: >7 semitonos entre dos cuadros seguidos con voz.

    Es la huella de los «gallos». Se cuentan por minuto de voz para comparar canciones de distinto largo.
    """
    import numpy as np

    f0 = np.asarray(f0, dtype=np.float64)
    voiced = f0 > 1
    semitones = 12 * np.log2(np.maximum(f0, 1e-5) / 440.0)
    both = voiced[1:] & voiced[:-1]
    jumps = np.abs(np.diff(semitones))[both]
    voiced_minutes = max(voiced.sum() / frames_per_second / 60.0, 1e-6)
    return {
        "saltos_por_min": round(float((jumps > 7).sum() / voiced_minutes), 1),
        "saltos_de_octava_por_min": round(float(((jumps > 10.5) & (jumps < 13.5)).sum() / voiced_minutes), 1),
        "minutos_con_voz": round(float(voiced_minutes), 2),
    }


@app.function(
    image=real_image,
    gpu="T4",
    secrets=translation_secrets,
    volumes={"/models": models_volume},
    timeout=1800,
)
def evaluate_translations(source_key: str, voices: dict) -> dict:
    """Compara versiones de una traducción con números.

    source_key: video original en R2. voices: {"nombre": clave R2 del voz.mp3 de cada versión}.
    Métricas por versión:
      - similitud_voz (0-1, más es mejor): parecido entre la voz nueva y la del cantante (Resemblyzer).
      - saltos_por_min / saltos_de_octava_por_min (menos es mejor): huella de los «gallos» (RMVPE).
    El "techo" compara dos mitades de la voz original: es lo máximo razonable para similitud_voz.
    """
    import sys

    import librosa
    import numpy as np
    from resemblyzer import VoiceEncoder, preprocess_wav

    from app.config import Config
    from app.pipeline import extract_audio, separate_vocals

    sys.path.insert(0, SEEDVC_DIR)
    from modules.rmvpe import RMVPE

    client, bucket = _r2()
    cfg = Config()
    encoder = VoiceEncoder("cuda")
    rmvpe = RMVPE(RMVPE_PATH, is_half=False, device="cuda")
    results: dict = {}

    with tempfile.TemporaryDirectory(prefix="evaluate-") as work:
        work_dir = Path(work)
        source = work_dir / ("source" + Path(source_key).suffix.lower())
        client.download_file(bucket, source_key, str(source))
        audio = extract_audio.extraer_audio(source, work_dir / "audio.wav", cfg)
        voice, _ = separate_vocals.separar_voces(audio, work_dir / "stems", cfg)
        reference = separate_vocals.voz_de_referencia(voice)

        original = preprocess_wav(librosa.load(str(reference), sr=16000)[0], source_sr=16000)
        half = len(original) // 2
        original_embed = encoder.embed_utterance(original)
        results["_techo"] = {
            "similitud_voz": round(float(np.dot(encoder.embed_utterance(original[:half]),
                                                encoder.embed_utterance(original[half:]))), 3),
        }

        for name, key in voices.items():
            path = work_dir / f"{name}.mp3"
            client.download_file(bucket, key, str(path))
            wav16 = librosa.load(str(path), sr=16000)[0]
            new_embed = encoder.embed_utterance(preprocess_wav(wav16, source_sr=16000))
            f0 = rmvpe.infer_from_audio(wav16, thred=0.03)
            results[name] = {
                "similitud_voz": round(float(np.dot(original_embed, new_embed)), 3),
                **_pitch_jumps(f0),
            }
            print(name, results[name])

    print("techo", results["_techo"])
    return results


# ─── Endpoint HTTP (controlador, sin GPU) ────────────────────────────────────

@app.function(image=controller_image, secrets=secrets, timeout=120)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def translate_video(request: dict):
    if request.get("action") == "status":
        job_id = request.get("remote_job_id")
        current = _status(job_id) if job_id else None
        if not current:
            return {"status": "failed", "progress_pct": 0, "stage": "",
                    "error_message": "Trabajo remoto no encontrado o expirado."}
        return _public_status(job_id, current)

    try:
        params = _validate_request(request)
    except ValueError as exc:
        return {"status": "failed", "progress_pct": 0, "stage": "", "error_message": str(exc)}

    # Idempotencia: el mismo client_job_id siempre devuelve el mismo trabajo remoto.
    client_key = f"client:{params['client_job_id']}"
    new_job_id = str(uuid.uuid4())
    if job_status.put(client_key, new_job_id, skip_if_exists=True):
        job_id = new_job_id
        job_status[job_id] = {
            "status": "queued",
            "stage": "en_cola",
            "progress_pct": 0,
            "mode": params["mode"],
            "outputs": {},
            "details": {},
            "error_message": None,
            "client_job_id": params["client_job_id"],
            "expires_at": _now() + JOB_TTL_SECONDS,
            "updated_at": _now(),
        }
        worker = run_real_translation if params["mode"] == "real" else run_simulated_translation
        try:
            worker.spawn(params, job_id)
        except Exception as exc:
            _set_status(job_id, status="failed", error_message=f"No se pudo lanzar el worker: {exc}"[:500])
    else:
        job_id = job_status.get(client_key)

    current = _status(job_id) or {"status": "failed", "progress_pct": 0,
                                  "error_message": "Trabajo remoto no encontrado."}
    return _public_status(job_id, current)
