"""Etapa 6 — mezclar la voz nueva con el instrumental y normalizar el volumen (loudnorm)."""
import json
import logging
import re
import subprocess
from pathlib import Path

from app.config import Config, obtener_config
from app.media import ffmpeg

log = logging.getLogger("worker.mezclar")


def _filtro_mezcla(cfg: Config) -> str:
    return (
        f"[0:a]aformat=channel_layouts=stereo,volume={cfg.ganancia_voz_db}dB[voz];"
        "[1:a]aformat=channel_layouts=stereo[inst];"
        "[voz][inst]amix=inputs=2:duration=longest:normalize=0"
    )


def medir_loudnorm(voz_nueva: Path, instrumental: Path, cfg: Config) -> dict | None:
    """MusicAI: primera pasada de loudnorm (solo mide). None si no se pudo medir."""
    filtro = _filtro_mezcla(cfg) + f",loudnorm=I={cfg.lufs_objetivo}:TP=-1.5:LRA=11:print_format=json[m]"
    try:
        r = subprocess.run([cfg.ffmpeg_bin, "-hide_banner", "-nostats", "-i", str(voz_nueva), "-i", str(instrumental),
                            "-filter_complex", filtro, "-map", "[m]", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("loudnorm: no se pudo medir (%s)", e)
        return None
    bloques = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr or "")
    if r.returncode != 0 or not bloques:
        log.warning("loudnorm: la medición no devolvió datos (código %d)", r.returncode)
        return None
    try:
        datos = json.loads(bloques[-1])
        medida = {k: float(datos[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
    if any(v != v or abs(v) == float("inf") for v in medida.values()):  # -inf en silencio total
        return None
    return medida


def mezclar(voz_nueva: Path, instrumental: Path, wav_salida: Path, cfg: Config | None = None) -> Path:
    """voz + instrumental → WAV estéreo 44.1 kHz normalizado a LUFS_OBJETIVO.

    MusicAI: con LOUDNORM_DOS_PASADAS primero se mide la sonoridad de la mezcla y luego se aplica UNA sola
    ganancia a toda la canción, con un limitador que solo actúa sobre los picos. En una pasada, loudnorm
    trabaja en modo dinámico y sube y baja el volumen a lo largo de la canción («bombeo»); su modo
    «linear=true» tampoco sirve: vuelve solo al dinámico si la canción tiene mucho rango o si subirla haría
    pasar el pico. Si la medición falla, se usa el método de una pasada de siempre.
    """
    cfg = cfg or obtener_config()
    wav_salida = Path(wav_salida)
    wav_salida.parent.mkdir(parents=True, exist_ok=True)
    norma = f"loudnorm=I={cfg.lufs_objetivo}:TP=-1.5:LRA=11"
    medida = medir_loudnorm(voz_nueva, instrumental, cfg) if cfg.loudnorm_dos_pasadas else None
    if medida:
        ganancia = max(-20.0, min(20.0, cfg.lufs_objetivo - medida["input_i"]))
        techo = 10 ** (-1.5 / 20)  # -1.5 dBFS
        norma = f"volume={ganancia:.2f}dB,alimiter=limit={techo:.4f}:attack=5:release=50:level=disabled"
        log.info("normalización en dos pasadas: entrada %.1f LUFS (pico %.1f dBTP, LRA %.1f) → ganancia "
                 "fija %+.1f dB y limitador a -1.5 dBFS", medida["input_i"], medida["input_tp"],
                 medida["input_lra"], ganancia)
    filtro = _filtro_mezcla(cfg) + f",{norma}[mezcla]"
    # loudnorm trabaja internamente a 192 kHz: se vuelve a 44.1 kHz al escribir
    ffmpeg(["-i", voz_nueva, "-i", instrumental, "-filter_complex", filtro, "-map", "[mezcla]",
            "-ar", 44100, "-c:a", "pcm_s16le", wav_salida], cfg)
    return wav_salida


def exportar_mp3(wav: Path, mp3_salida: Path, cfg: Config | None = None) -> Path:
    """WAV → MP3 (para entregar la pista de voz sola)."""
    cfg = cfg or obtener_config()
    mp3_salida = Path(mp3_salida)
    mp3_salida.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg(["-i", wav, "-c:a", "libmp3lame", "-b:a", "192k", mp3_salida], cfg)
    return mp3_salida
