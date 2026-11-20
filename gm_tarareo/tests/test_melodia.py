import pytest

from app.modelos import MotivoFallo
from app.pipeline.excepciones import ErrorAudioInvalido
from app.pipeline.ingesta import ingestar
from app.pipeline.melodia import cargar_modelo, extraer_melodia, modelo_cargado
from app.pipeline.preprocesado import preprocesar

# Estos tests corren basic-pitch de verdad (carga TensorFlow, tarda
# bastantes segundos). Para iterar rápido: pytest -m "not slow"
pytestmark = pytest.mark.slow


def test_el_modelo_se_carga_una_sola_vez_y_se_reutiliza():
    primero = cargar_modelo()

    assert modelo_cargado()
    assert cargar_modelo() is primero


def test_extraer_melodia_audio_real_devuelve_notas(audio_real, directorio_trabajo, config):
    wav = ingestar(audio_real, directorio_trabajo, config.frecuencia_muestreo_hz)
    wav_preprocesado, _ = preprocesar(wav, directorio_trabajo, config)

    notas, confianza = extraer_melodia(wav_preprocesado, config)

    assert len(notas) > 0
    assert confianza >= config.melodia_confianza_minima


def test_extraer_melodia_ruido_falla_con_motivo_sin_melodia_clara(audio_ruido, directorio_trabajo, config):
    wav = ingestar(audio_ruido, directorio_trabajo, config.frecuencia_muestreo_hz)
    wav_preprocesado, _ = preprocesar(wav, directorio_trabajo, config)

    with pytest.raises(ErrorAudioInvalido) as info:
        extraer_melodia(wav_preprocesado, config)

    assert info.value.motivo == MotivoFallo.SIN_MELODIA_CLARA
