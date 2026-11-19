"""
Etapa 3 del pipeline: MELODÍA.

Corre basic-pitch sobre el audio preprocesado y devuelve las notas crudas
(sin limpiar todavía, eso es tarea de limpieza.py).

Acá también se decide el tercer motivo de fallo, SIN_MELODIA_CLARA: es la
única etapa que puede distinguir "hay energía" (ruido) de "hay una melodía"
(tarareo), porque basic-pitch fue entrenado exactamente para eso.
"""

from __future__ import annotations

import logging
import os
import threading
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.modelos import MotivoFallo
from app.pipeline.excepciones import ErrorAudioInvalido

# Tiene que ir antes de importar basic_pitch/tensorflow para que surta efecto.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
warnings.filterwarnings("ignore", module="basic_pitch")
logging.getLogger("tensorflow").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotaCruda:
    """Una nota tal como la devuelve basic-pitch, antes de limpieza.py."""

    nota: int  # pitch MIDI
    inicio: float  # segundos
    fin: float  # segundos
    amplitud: float  # 0-1, usado como proxy de confianza
    pitch_bends: tuple[float, ...] = ()  # semitonos, sin inferencia adicional


_modelo: Any = None
_candado_modelo = threading.Lock()


def cargar_modelo() -> Any:
    """
    Carga el modelo de basic-pitch una sola vez por proceso y lo reutiliza.

    Antes, `predict()` recibía la ruta del modelo y lo recargaba en cada job
    (~5 s con TensorFlow, ~20 s la primera vez porque además importa TF).
    Ahora main.py lo llama al arrancar el servidor, y probar.py y los tests
    lo cargan solos la primera vez que extraen una melodía.

    El candado evita que dos jobs que arrancan a la vez lo carguen dos
    veces. Compartir la instancia entre hilos es seguro con el backend de
    TensorFlow (y con ONNX Runtime, si se adopta): la inferencia de una
    SavedModel no modifica estado. No lo sería con TFLite, que no usamos.

    Devuelve `Any` para no importar basic_pitch (y TensorFlow) al importar
    este módulo: eso haría lento cualquier import de app.pipeline.
    """
    global _modelo
    if _modelo is None:
        with _candado_modelo:
            if _modelo is None:
                from basic_pitch import ICASSP_2022_MODEL_PATH
                from basic_pitch.inference import Model

                logger.info("Cargando el modelo de basic-pitch desde %s", ICASSP_2022_MODEL_PATH)
                _modelo = Model(ICASSP_2022_MODEL_PATH)
    return _modelo


def modelo_cargado() -> bool:
    """Si el modelo ya está en memoria. Lo usa /salud sin disparar la carga."""
    return _modelo is not None


def extraer_notas_crudas(ruta_wav: Path) -> list[NotaCruda]:
    from basic_pitch.inference import predict

    _, _, eventos = predict(str(ruta_wav), cargar_modelo())

    notas = [
        NotaCruda(nota=int(pitch), inicio=float(inicio), fin=float(fin), amplitud=float(amplitud),
                  pitch_bends=tuple(float(b) / 3 for b in bends) if bends is not None else ())
        # basic-pitch/note_creation.py: get_pitch_bends devuelve tercios de semitono.
        for inicio, fin, pitch, amplitud, bends in eventos
    ]
    return sorted(notas, key=lambda n: n.inicio)


def extraer_melodia(ruta_wav: Path, config) -> tuple[list[NotaCruda], float]:
    """
    Punto de entrada de la etapa. Devuelve (notas_crudas, confianza_promedio).

    confianza_promedio es la amplitud media de TODAS las notas crudas (antes
    de cualquier limpieza) — refleja qué tan clara fue la señal de entrada,
    no cuánto sobrevivió a la limpieza.
    """
    notas = extraer_notas_crudas(ruta_wav)
    confianza_promedio = sum(n.amplitud for n in notas) / len(notas) if notas else 0.0

    logger.info(
        "basic-pitch devolvió %d notas crudas, confianza promedio %.3f (umbral mínimo %.2f)",
        len(notas), confianza_promedio, config.melodia_confianza_minima,
    )

    # Además de la confianza, un mínimo de notas: el ruido blanco a veces da
    # 1-2 notas con confianza alta por casualidad (medido 2026-11-14: semilla
    # 4 de anoisesrc → 2 notas, 0.437). Los tarareos reales dan 9-55 crudas.
    valida = len(notas) >= config.analisis_notas_minimas and confianza_promedio >= config.melodia_confianza_minima
    if (not valida and config.interpretacion_verificar_alturas
            and len(notas) >= config.analisis_notas_minimas and confianza_promedio >= .2):
        from app.pipeline.interpretacion import verificar_alturas

        _, confirmadas, _ = verificar_alturas(ruta_wav, notas)
        valida = len(confirmadas) >= max(config.analisis_notas_minimas, .7 * len(notas))
        if valida:
            logger.info("Se acepta la melodía por evidencia acústica en %d notas", len(confirmadas))
    if not valida:
        raise ErrorAudioInvalido(
            MotivoFallo.SIN_MELODIA_CLARA,
            "No se detectó una melodía clara (parece ruido o voz sin tono definido). "
            "Probá tararear más fuerte y sostener las notas.",
        )

    return notas, confianza_promedio
