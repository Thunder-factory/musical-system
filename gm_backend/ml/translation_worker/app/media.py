"""Envoltorios mínimos de FFmpeg / ffprobe usados por varias etapas."""
import json
import subprocess
from functools import lru_cache
from pathlib import Path

from app.config import Config
from app.errores import ErrorPipeline


def ejecutar(cmd: list[str], timeout: int = 1800) -> str:
    """Ejecuta un comando y devuelve su stdout; lanza ErrorPipeline si falla."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except OSError as e:
        raise ErrorPipeline(f"no se pudo ejecutar {cmd[0]}: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise ErrorPipeline(f"{Path(cmd[0]).name} superó {timeout}s") from e
    if r.returncode != 0:
        raise ErrorPipeline(f"{Path(cmd[0]).name} falló: {r.stderr.strip()[-800:]}")
    return r.stdout


def ffmpeg(args: list[str], cfg: Config) -> None:
    ejecutar([cfg.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)])


def sondear(ruta: Path, cfg: Config) -> dict:
    """ffprobe en JSON: {'format': {...}, 'streams': [...]}."""
    salida = ejecutar([cfg.ffprobe_bin, "-v", "error", "-print_format", "json",
                       "-show_format", "-show_streams", str(ruta)], timeout=60)
    return json.loads(salida)


def duracion_s(ruta: Path, cfg: Config) -> float:
    return float(sondear(ruta, cfg)["format"]["duration"])


@lru_cache
def _filtros(ffmpeg_bin: str) -> str:
    return ejecutar([ffmpeg_bin, "-hide_banner", "-filters"], timeout=30)


def tiene_filtro(nombre: str, cfg: Config) -> bool:
    return f" {nombre} " in _filtros(cfg.ffmpeg_bin)
