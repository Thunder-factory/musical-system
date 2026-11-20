"""Etapa 1 — validar el video y extraer su audio a WAV 44.1 kHz estéreo (FFmpeg)."""
from pathlib import Path

from app.config import Config, obtener_config
from app.errores import EntradaInvalida, ErrorPipeline
from app.media import ffmpeg, sondear

FRECUENCIA = 44100


def validar_video(video: Path, cfg: Config | None = None) -> dict:
    """Comprueba formato, tamaño, duración y pista de audio. Devuelve {duracion_s, tamano_mb}."""
    cfg = cfg or obtener_config()
    video = Path(video)
    if not video.is_file():
        raise EntradaInvalida(f"no existe el archivo: {video.name}")
    extension = video.suffix.lower().lstrip(".")
    if extension not in cfg.formatos:
        raise EntradaInvalida(f"formato .{extension} no soportado (válidos: {', '.join(cfg.formatos)})")
    tamano_mb = video.stat().st_size / (1024 * 1024)
    if tamano_mb > cfg.max_tamano_mb:
        raise EntradaInvalida(f"el video pesa {tamano_mb:.0f} MB (máximo {cfg.max_tamano_mb} MB)")
    try:
        info = sondear(video, cfg)
        duracion = float(info["format"]["duration"])
    except (ErrorPipeline, KeyError, ValueError) as e:
        raise EntradaInvalida("el archivo no es un video legible") from e
    tipos = {s.get("codec_type") for s in info.get("streams", [])}
    if "video" not in tipos:
        raise EntradaInvalida("el archivo no tiene pista de video")
    if "audio" not in tipos:
        raise EntradaInvalida("el video no tiene pista de audio")
    if duracion > cfg.max_duracion_s:
        raise EntradaInvalida(f"el video dura {duracion:.0f} s (máximo {cfg.max_duracion_s} s)")
    return {"duracion_s": duracion, "tamano_mb": tamano_mb}


def extraer_audio(video: Path, wav_salida: Path, cfg: Config | None = None) -> Path:
    """video → WAV PCM 16 bits, 44.1 kHz, estéreo."""
    cfg = cfg or obtener_config()
    wav_salida = Path(wav_salida)
    wav_salida.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg(["-i", video, "-vn", "-map", "0:a:0", "-ac", "2", "-ar", FRECUENCIA,
            "-c:a", "pcm_s16le", wav_salida], cfg)
    return wav_salida
