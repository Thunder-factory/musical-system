"""Etapa 5b (opcional, fase 7.3) — convertir el timbre de la voz sintetizada con un modelo RVC.

Se aplica a la pista de voz ya armada (XTTS + interjecciones), así toda la voz queda con el mismo
timbre. RVC vive en su propio entorno (.venv-rvc, Applio): se llama como proceso aparte, de modo que
sus dependencias (torch 2.11) no chocan con las del worker (torch 2.5.1) y la VRAM se libera sola al
terminar el proceso.
"""
import logging
import subprocess
import time
from pathlib import Path

from app.config import Config, obtener_config
from app.errores import ErrorPipeline
from app.media import ffmpeg
from app.pipeline.synthesize import FRECUENCIA

log = logging.getLogger("worker.rvc")


def comando_rvc(entrada: Path, salida: Path, cfg: Config) -> list[str]:
    """Llamada a `core.py infer` de Applio con los ajustes de RVC_* del .env."""
    return [
        str(cfg.ruta(cfg.rvc_python)), "core.py", "infer",
        "--input-path", str(entrada), "--output-path", str(salida),
        "--pth-path", str(cfg.ruta(Path(cfg.rvc_modelo))),
        "--index-path", str(cfg.ruta(Path(cfg.rvc_indice))) if cfg.rvc_indice else "",
        "--pitch", str(cfg.rvc_tono), "--index-rate", f"{cfg.rvc_index_rate:g}",
        "--protect", f"{cfg.rvc_protect:g}", "--f0-method", "rmvpe",
        "--embedder-model", "contentvec", "--export-format", "WAV",
    ]


def verificar_rvc(cfg: Config) -> None:
    """Falla con un mensaje claro si falta algo antes de gastar tiempo."""
    faltan = [nombre for nombre, ruta in (("RVC_PYTHON", cfg.ruta(cfg.rvc_python)),
                                          ("RVC_APPLIO", cfg.ruta(cfg.rvc_applio) / "core.py"),
                                          ("RVC_MODELO", cfg.ruta(Path(cfg.rvc_modelo or "-"))))
              if not ruta.is_file()]
    if cfg.rvc_indice and not cfg.ruta(Path(cfg.rvc_indice)).is_file():
        faltan.append("RVC_INDICE")
    if faltan:
        raise ErrorPipeline(f"RVC activo pero no se encuentra: {', '.join(faltan)} (revisa el .env)")


def convertir_voz(wav_entrada: Path, wav_salida: Path, cfg: Config | None = None) -> Path:
    """voz sintetizada → misma voz con el timbre del modelo RVC (44.1 kHz mono, como la entrada)."""
    cfg = cfg or obtener_config()
    verificar_rvc(cfg)
    wav_entrada, wav_salida = Path(wav_entrada).resolve(), Path(wav_salida).resolve()
    crudo = wav_salida.with_name(wav_salida.stem + "_rvc_crudo.wav")
    inicio = time.perf_counter()
    try:
        r = subprocess.run(comando_rvc(wav_entrada, crudo, cfg), cwd=cfg.ruta(cfg.rvc_applio),
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=cfg.rvc_timeout_s)
    except subprocess.TimeoutExpired:
        raise ErrorPipeline(f"RVC tardó más de {cfg.rvc_timeout_s} s")
    if r.returncode != 0 or not crudo.is_file():
        ultimas = "\n".join((r.stderr or r.stdout).strip().splitlines()[-5:])
        raise ErrorPipeline(f"RVC falló (código {r.returncode}): {ultimas}")
    # Applio entrega a la frecuencia del modelo (40 kHz): se vuelve a la del resto del pipeline
    ffmpeg(["-i", crudo, "-ac", "1", "-ar", FRECUENCIA, "-c:a", "pcm_s16le", wav_salida], cfg)
    crudo.unlink(missing_ok=True)
    log.info("RVC: timbre convertido con %s en %.1f s", Path(cfg.rvc_modelo).name, time.perf_counter() - inicio)
    return wav_salida
