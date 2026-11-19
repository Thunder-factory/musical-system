"""
Calentamiento: compila de antemano las funciones que librosa acelera con numba.

numba compila cada función la primera vez que se usa en un proceso. Medido en
Docker (2026-11-14): el primer job tardaba 104 s y el segundo 19 s; la
diferencia era numba compilando lo que usan el preprocesado, basic-pitch y el
análisis de tempo.

Se llama dos veces:
- al CONSTRUIR la imagen (Dockerfile), con NUMBA_CACHE_DIR apuntando a una
  carpeta de la imagen: la compilación queda guardada y el contenedor arranca
  ya compilado;
- al ARRANCAR el worker (lifespan de main.py), por si el contenedor corre en
  otra CPU y numba descarta la caché: así lo paga el arranque, nunca el
  primer usuario.

Corre las mismas funciones del pipeline sobre una melodía sintética de 10 s
(sin ffmpeg ni FluidSynth: solo lo que usa numba).
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

FRECUENCIA_HZ = 22050
DURACION_SEGUNDOS = 10.0


def _melodia_sintetica() -> np.ndarray:
    """Do-Re-Mi-Fa-Sol en notas de 0.5 s: una melodía clara, para que basic-pitch tenga algo que detectar."""
    notas_midi = [60, 62, 64, 65, 67, 65, 64, 62] * 3
    muestras_por_nota = int(0.5 * FRECUENCIA_HZ)
    t = np.arange(muestras_por_nota) / FRECUENCIA_HZ
    envolvente = np.minimum(1.0, t / 0.02) * np.minimum(1.0, (t[-1] - t) / 0.05)
    tramos = [0.4 * np.sin(2 * np.pi * 440.0 * 2 ** ((n - 69) / 12) * t) * envolvente for n in notas_midi]
    audio = np.concatenate(tramos)
    return audio[: int(DURACION_SEGUNDOS * FRECUENCIA_HZ)].astype(np.float32)


def calentar(config=None) -> float:
    """Ejecuta preprocesado, basic-pitch y el tempo de librosa. Devuelve los segundos que tardó."""
    from app.config import obtener_configuracion
    from app.pipeline.analisis import tempo_librosa
    from app.pipeline.excepciones import ErrorPipeline
    from app.pipeline.interpretacion import medir_alturas
    from app.pipeline.melodia import extraer_melodia
    from app.pipeline.preprocesado import preprocesar

    config = config or obtener_configuracion()
    inicio = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="calentamiento-") as carpeta:
        directorio = Path(carpeta)
        wav = directorio / "melodia.wav"
        sf.write(str(wav), _melodia_sintetica(), FRECUENCIA_HZ)
        try:
            preprocesado, _ = preprocesar(wav, directorio, config)
            extraer_melodia(preprocesado, config)
            tempo_librosa(preprocesado)
            if config.interpretacion_verificar_alturas:
                medir_alturas(preprocesado)
        except ErrorPipeline:
            # Si el audio sintético no pasara alguna validación, igual ya se
            # compiló lo que se ejecutó hasta ahí; no es motivo para no arrancar.
            logger.warning("El calentamiento no completó todas las etapas", exc_info=True)
    segundos = time.perf_counter() - inicio
    logger.info("Calentamiento de numba listo en %.1f s", segundos)
    return segundos


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
    calentar()
