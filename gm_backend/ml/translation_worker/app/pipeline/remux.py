"""Etapa 7 — reemplazar el audio del video sin recodificar la imagen (-c:v copy)."""
import logging
from pathlib import Path

from app.config import Config, obtener_config
from app.errores import ErrorPipeline
from app.media import ffmpeg

log = logging.getLogger("worker.remux")


def remux(video: Path, audio: Path, mp4_salida: Path, cfg: Config | None = None) -> Path:
    """video original (sin su audio) + audio nuevo → MP4."""
    cfg = cfg or obtener_config()
    mp4_salida = Path(mp4_salida)
    mp4_salida.parent.mkdir(parents=True, exist_ok=True)
    comunes = ["-i", video, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    try:
        ffmpeg([*comunes, "-c:v", "copy", mp4_salida], cfg)
    except ErrorPipeline as e:
        # p. ej. un webm con VP8, que el contenedor MP4 no admite: ahí sí toca recodificar
        log.warning("no se pudo copiar el video tal cual (%s): se recodifica a H.264", e)
        ffmpeg([*comunes, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", mp4_salida], cfg)
    return mp4_salida
