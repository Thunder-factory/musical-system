"""Etapa 5b (fase 7, paso 3) — que la voz nueva cante con la voz y la melodía del cantante del video.

Seed-VC (modo canto, sin entrenamiento) convierte la pista sintetizada usando como referencia unos segundos
de la voz original separada. La curva de tono no sale de XTTS (que habla) sino de la voz original en los
mismos instantes: así la frase traducida sigue la melodía de la canción. Corre como proceso aparte
(scripts/externos/seedvc_cantar.py) con el Python del worker, para liberar la VRAM al terminar.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path

from app.config import RAIZ, Config, obtener_config
from app.errores import ErrorPipeline
from app.pipeline.synthesize import preparar_referencia

log = logging.getLogger("worker.cantar")

SCRIPT = RAIZ / "scripts" / "externos" / "seedvc_cantar.py"
MELODIAS = ("original", "fuente")


def comando(fuente: Path, original: Path, referencia: Path, salida: Path, cfg: Config) -> list[str]:
    return [sys.executable, str(SCRIPT), "--fuente", str(fuente), "--original", str(original),
            "--referencia", str(referencia), "--salida", str(salida),
            "--rmvpe", str(cfg.ruta(cfg.rvc_applio) / "rvc" / "models" / "predictors" / "rmvpe.pt"),
            "--melodia", cfg.canto_melodia, "--pasos", str(cfg.canto_pasos), "--cfg", f"{cfg.canto_cfg:g}",
            "--semitonos", str(cfg.canto_semitonos)] + (["--limpiar"] if cfg.canto_limpiar else [])


def cantar(voz_nueva: Path, voz_original: Path, frases: list[dict], wav_salida: Path,
           cfg: Config | None = None) -> Path:
    """voz sintetizada (alineada con la canción) → la misma letra cantada con la voz y melodía originales."""
    cfg = cfg or obtener_config()
    if cfg.canto_melodia not in MELODIAS:
        raise ErrorPipeline(f"CANTO_MELODIA={cfg.canto_melodia} no existe (válidos: {', '.join(MELODIAS)})")
    carpeta = cfg.ruta(cfg.seedvc_dir)
    if not (carpeta / "inference.py").is_file():
        raise ErrorPipeline(f"CANTO activo pero no está Seed-VC en SEEDVC_DIR={cfg.seedvc_dir}")
    wav_salida = Path(wav_salida).resolve()
    referencia = preparar_referencia(voz_original, frases, wav_salida.with_name("referencia_canto.wav"),
                                     max_s=cfg.canto_referencia_s)
    entorno = {**os.environ, "HF_HOME": str(cfg.ruta_modelos / "huggingface"),
               "HF_HUB_CACHE": str(cfg.ruta_modelos / "huggingface" / "hub"), "HF_HUB_OFFLINE": "1",
               "PYTHONIOENCODING": "utf-8"}
    try:
        r = subprocess.run(comando(Path(voz_nueva).resolve(), Path(voz_original).resolve(), referencia, wav_salida, cfg),
                           cwd=carpeta, env=entorno, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=cfg.canto_timeout_s)
    except subprocess.TimeoutExpired:
        raise ErrorPipeline(f"Seed-VC tardó más de {cfg.canto_timeout_s} s")
    finally:
        referencia.unlink(missing_ok=True)
    fin = [l for l in r.stdout.splitlines() if l.startswith("OK ")]
    if r.returncode != 0 or not fin or not wav_salida.is_file():
        ultimas = "\n".join((r.stderr or r.stdout).strip().splitlines()[-6:])
        raise ErrorPipeline(f"Seed-VC falló (código {r.returncode}): {ultimas}")
    _, segundos, cobertura = fin[-1].split()
    log.info("canto (Seed-VC): %s s, melodía %s (cuadros con nota original: %s)", segundos, cfg.canto_melodia, cobertura)
    limpieza = [l for l in (r.stderr or "").splitlines() if l.startswith("MELODIA ")]
    if limpieza:
        log.info("canto: melodía limpiada (%s)", limpieza[-1].removeprefix("MELODIA "))
    trozos = [l for l in (r.stderr or "").splitlines() if l.startswith("TROZOS ")]
    if trozos:  # MusicAI: dónde se unen los trozos de Seed-VC (para localizar saltos de timbre o volumen)
        log.info("canto: %s", trozos[-1].removeprefix("TROZOS "))
    return wav_salida
