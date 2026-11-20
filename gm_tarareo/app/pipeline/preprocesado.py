"""
Etapa 2 del pipeline: PREPROCESADO.

Toma el WAV ya normalizado en formato por ingesta.py y lo deja listo para
basic-pitch: recorta silencios de los bordes, valida que la duración y la
señal sirvan, y normaliza el volumen.

Acá se resuelven 2 de los 3 motivos de fallo (MotivoFallo): duración y
silencio. El tercero (SIN_MELODIA_CLARA, ruido sin tono) no se puede
decidir con estas señales simples — se detecta en melodia.py después de
correr basic-pitch, que es la única forma confiable de distinguir "hay
energía" de "hay una melodía".
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

from app.modelos import MotivoFallo
from app.pipeline.excepciones import ErrorAudioInvalido

logger = logging.getLogger(__name__)

NOMBRE_AUDIO_PREPROCESADO = "audio_preprocesado.wav"

# Pico objetivo tras normalizar, con margen para no clipear en el render final.
PICO_OBJETIVO = 0.89  # ~ -1 dBFS


def calcular_dbfs(audio: np.ndarray) -> float:
    """RMS en dBFS. -inf si el audio es silencio digital puro (rms == 0)."""
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    if rms <= 0.0:
        return float("-inf")
    return 20.0 * float(np.log10(rms))


VENTANA_NIVEL_SEGUNDOS = 0.05
PERCENTIL_NIVEL_ACTIVO = 95


def calcular_dbfs_activo(audio: np.ndarray, sr: int) -> float:
    """
    Nivel de los tramos donde hay sonido: percentil 95 del RMS en ventanas de 50 ms.

    Por qué no el RMS de toda la grabación: un tarareo tiene pausas entre
    frases, y en una grabación bajita esas pausas arrastran el promedio.
    Medido con el lote de prueba (2026-11-14): `08 T.m4a` es un tarareo real
    (picos de -25 dB) pero su RMS global daba -45.1 dBFS porque la mitad del
    audio está a -69 dB, y se rechazaba como silencio. Con el p95 de
    ventanas, las 10 grabaciones reales quedan entre -19 y -37 dBFS y una
    sala vacía sintética (micrófono abierto, nadie tarareando) entre -55 y
    -72: el mismo umbral de -45 separa los dos grupos con 8-10 dB de margen.
    """
    muestras_ventana = max(1, int(VENTANA_NIVEL_SEGUNDOS * sr))
    cantidad = len(audio) // muestras_ventana
    if cantidad == 0:
        return calcular_dbfs(audio)

    ventanas = audio[: cantidad * muestras_ventana].reshape(cantidad, muestras_ventana)
    rms = np.sqrt(np.mean(np.square(ventanas, dtype=np.float64), axis=1))
    rms_activo = float(np.percentile(rms, PERCENTIL_NIVEL_ACTIVO))
    if rms_activo <= 0.0:
        return float("-inf")
    return 20.0 * float(np.log10(rms_activo))


def recortar_silencios(audio: np.ndarray, sr: int, umbral_silencio_dbfs: float) -> np.ndarray:
    """Recorta silencio de los bordes (no del medio) usando el mismo umbral que la validación."""
    import librosa

    # librosa.effects.trim usa top_db relativo al pico del audio, no dBFS absoluto,
    # así que lo acotamos a un mínimo razonable para no recortar de más un audio ya bajo.
    top_db = max(10.0, -umbral_silencio_dbfs)
    recortado, _ = librosa.effects.trim(audio, top_db=top_db)
    return recortado


def normalizar_volumen(audio: np.ndarray) -> np.ndarray:
    """Normaliza por pico a PICO_OBJETIVO. Asume que ya se validó que hay señal."""
    pico_actual = float(np.max(np.abs(audio)))
    if pico_actual == 0.0:
        return audio
    return audio * (PICO_OBJETIVO / pico_actual)


def validar_duracion(duracion_segundos: float, minima: float, *, tras_recortar: bool = False) -> None:
    if duracion_segundos < minima:
        que_mide = "tiene solo" if tras_recortar else "dura"
        sufijo = " de sonido útil (sin contar los silencios)" if tras_recortar else ""
        raise ErrorAudioInvalido(
            MotivoFallo.GRABACION_MUY_CORTA,
            f"La grabación {que_mide} {duracion_segundos:.1f}s{sufijo}, se necesitan al menos "
            f"{minima:.0f}s para detectar tempo y melodía de forma confiable.",
        )


def validar_senal(audio_recortado: np.ndarray, sr: int, umbral_silencio_dbfs: float) -> None:
    nivel_dbfs = calcular_dbfs_activo(audio_recortado, sr)
    logger.info("Nivel de los tramos con sonido (p95): %.1f dBFS (umbral %.1f)", nivel_dbfs, umbral_silencio_dbfs)
    if audio_recortado.size == 0 or nivel_dbfs < umbral_silencio_dbfs:
        raise ErrorAudioInvalido(
            MotivoFallo.SIN_SENAL,
            "No se detectó señal de audio (parece silencio). Grabá de nuevo "
            "asegurándote de que el micrófono esté activo y cerca de la boca.",
        )


def preprocesar(ruta_wav: Path, directorio_job: Path, config) -> tuple[Path, float]:
    """
    Orquesta la etapa: carga, valida duración, recorta silencios, valida
    señal, normaliza volumen y escribe el resultado.

    Devuelve (ruta_audio_preprocesado, duracion_segundos_final).
    """
    audio, sr = sf.read(str(ruta_wav), dtype="float32", always_2d=False)
    duracion_original = len(audio) / sr

    validar_duracion(duracion_original, config.duracion_minima_segundos)

    if duracion_original > config.duracion_maxima_segundos:
        muestras_max = int(config.duracion_maxima_segundos * sr)
        logger.warning(
            "Audio de %.1fs excede el máximo de %.0fs, se recorta a los primeros %.0fs",
            duracion_original, config.duracion_maxima_segundos, config.duracion_maxima_segundos,
        )
        audio = audio[:muestras_max]

    audio_recortado = recortar_silencios(audio, sr, config.umbral_silencio_dbfs)
    validar_senal(audio_recortado, sr, config.umbral_silencio_dbfs)
    # Segunda validación de duración, sobre el audio ya recortado: 4s de
    # tarareo + 6s de silencio pasan el chequeo de arriba pero no alcanzan
    # para detectar tempo. Va después de validar_senal para que el silencio
    # puro siga fallando como SIN_SENAL y no como GRABACION_MUY_CORTA.
    validar_duracion(len(audio_recortado) / sr, config.duracion_minima_segundos, tras_recortar=True)
    audio_normalizado = normalizar_volumen(audio_recortado)

    directorio_job.mkdir(parents=True, exist_ok=True)
    ruta_salida = directorio_job / NOMBRE_AUDIO_PREPROCESADO
    sf.write(str(ruta_salida), audio_normalizado, sr)

    duracion_final = len(audio_normalizado) / sr
    logger.info(
        "Preprocesado listo: %s (%.1fs, %.1f dBFS)",
        ruta_salida, duracion_final, calcular_dbfs(audio_normalizado),
    )
    return ruta_salida, duracion_final
