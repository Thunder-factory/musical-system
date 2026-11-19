from pathlib import Path

import numpy as np
import pytest

from app.modelos import MotivoFallo
from app.pipeline.excepciones import ErrorAudioInvalido
from app.pipeline.ingesta import ingestar
from app.pipeline.preprocesado import (
    calcular_dbfs,
    calcular_dbfs_activo,
    normalizar_volumen,
    preprocesar,
    validar_senal,
)


def test_calcular_dbfs_silencio_es_menos_infinito():
    assert calcular_dbfs(np.zeros(1000, dtype=np.float32)) == float("-inf")


def test_calcular_dbfs_pico_maximo_es_cero():
    audio = np.ones(1000, dtype=np.float32)
    assert calcular_dbfs(audio) == pytest.approx(0.0, abs=0.01)


def test_normalizar_volumen_lleva_al_pico_objetivo():
    audio = np.array([0.1, -0.2, 0.05], dtype=np.float32)
    normalizado = normalizar_volumen(audio)
    assert np.max(np.abs(normalizado)) == pytest.approx(0.89, abs=0.001)


def test_normalizar_volumen_no_rompe_con_silencio():
    audio = np.zeros(100, dtype=np.float32)
    assert np.all(normalizar_volumen(audio) == 0.0)


def test_preprocesar_audio_real(audio_real, directorio_trabajo, config):
    wav = ingestar(audio_real, directorio_trabajo, config.frecuencia_muestreo_hz)
    ruta, duracion = preprocesar(wav, directorio_trabajo, config)

    assert ruta.exists()
    assert 15.0 < duracion < 18.0  # el archivo real mide ~16.8s


def test_preprocesar_silencio_falla_con_motivo_sin_senal(audio_silencio, directorio_trabajo, config):
    with pytest.raises(ErrorAudioInvalido) as info:
        preprocesar(audio_silencio, directorio_trabajo, config)
    assert info.value.motivo == MotivoFallo.SIN_SENAL


def test_preprocesar_corto_falla_con_motivo_grabacion_muy_corta(audio_corto, directorio_trabajo, config):
    with pytest.raises(ErrorAudioInvalido) as info:
        preprocesar(audio_corto, directorio_trabajo, config)
    assert info.value.motivo == MotivoFallo.GRABACION_MUY_CORTA


def test_preprocesar_ruido_no_falla_en_esta_etapa(audio_ruido, directorio_trabajo, config):
    # el ruido blanco tiene señal (no es silencio), así que esta etapa lo
    # deja pasar; SIN_MELODIA_CLARA se decide recién en melodia.py
    ruta, duracion = preprocesar(audio_ruido, directorio_trabajo, config)
    assert ruta.exists()
    assert duracion > 0


def test_preprocesar_poco_sonido_util_falla_aunque_el_archivo_sea_largo(
    audio_corto_con_silencio, directorio_trabajo, config
):
    # 10s de archivo pero solo 4s de sonido: la duración mínima tiene que
    # medirse después de recortar los silencios, no sobre el archivo entero.
    with pytest.raises(ErrorAudioInvalido) as info:
        preprocesar(audio_corto_con_silencio, directorio_trabajo, config)
    assert info.value.motivo == MotivoFallo.GRABACION_MUY_CORTA
    assert "sonido útil" in info.value.mensaje


SR = 22050


def _tarareo_bajito_con_pausas() -> np.ndarray:
    """
    Frases de 1 s de tono a ~-39.5 dBFS separadas por pausas de 4 s a ~-70
    dBFS: la forma de `08 T.m4a`, un tarareo real grabado bajito (voz a
    ~-37 dB, la mitad del audio en pausa a -69 dB).
    """
    rng = np.random.default_rng(0)
    t = np.arange(SR) / SR
    frase = 0.015 * np.sin(2 * np.pi * 220 * t)
    pausa = 0.0003 * rng.standard_normal(4 * SR)
    return np.concatenate([np.concatenate([frase, pausa]) for _ in range(5)]).astype(np.float32)


def test_tarareo_bajito_con_pausas_no_es_silencio():
    audio = _tarareo_bajito_con_pausas()

    # El criterio viejo (RMS de toda la grabación) lo rechazaba como silencio...
    assert calcular_dbfs(audio) < -45.0
    # ...pero los tramos con voz están muy por encima del umbral.
    assert calcular_dbfs_activo(audio, SR) > -40.0
    validar_senal(audio, SR, -45.0)  # no lanza


def test_sala_vacia_con_ruido_de_fondo_es_silencio():
    """Micrófono abierto sin nadie tarareando: ruido de fondo a ~-60 dBFS."""
    ruido_de_fondo = (0.001 * np.random.default_rng(1).standard_normal(10 * SR)).astype(np.float32)

    with pytest.raises(ErrorAudioInvalido) as info:
        validar_senal(ruido_de_fondo, SR, -45.0)
    assert info.value.motivo == MotivoFallo.SIN_SENAL


def test_grabacion_real_bajita_08_pasa_el_preprocesado(directorio_trabajo, config):
    """Regresión del lote del 2026-11-14: `08 T.m4a` se rechazaba como silencio siendo un tarareo."""
    ruta = Path(__file__).resolve().parent / "audio" / "08 T.m4a"
    if not ruta.exists():
        pytest.skip(f"Falta la grabación: {ruta}")

    wav = ingestar(ruta, directorio_trabajo, config.frecuencia_muestreo_hz)
    _, duracion = preprocesar(wav, directorio_trabajo, config)

    assert duracion >= config.duracion_minima_segundos
