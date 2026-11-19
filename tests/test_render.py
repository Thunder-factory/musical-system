"""
Tests de la etapa 8 (render).

La normalización y el MP3 se prueban con audio sintético (solo ffmpeg). El
render completo con FluidSynth se saltea si la máquina no lo tiene.
"""

import json
import re
import subprocess

import pretty_midi
import pytest

from app.config import Configuracion
from app.modelos import NotaMusical
from app.pipeline.analisis import analizar
from app.pipeline.armonia import armonizar
from app.pipeline.arreglo import arreglar
from app.pipeline.estilo import inferir_estilo
from app.pipeline.excepciones import ErrorRender
from app.pipeline.render import (
    duracion_audio,
    normalizar_y_codificar,
    renderizar,
    resolver_fluidsynth,
    resolver_soundfont,
)
from app.pipeline.salida import MEZCLA_POR_ROL, escribir_arreglo_midi


def _medir_lufs(ruta) -> tuple[float, float]:
    """Medición independiente del resultado (otra pasada de loudnorm sobre el MP3)."""
    salida = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta), "-af", "loudnorm=print_format=json",
         "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", salida.stderr)[-1])
    return float(m["input_i"]), float(m["input_tp"])


@pytest.fixture(scope="module")
def wav_bajito(tmp_path_factory):
    """12 s de acordes sintéticos en estéreo, grabados muy bajos (como un render con ganancia baja)."""
    ruta = tmp_path_factory.mktemp("render") / "bajito.wav"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=220:duration=12:sample_rate=44100",
         "-f", "lavfi", "-i", "sine=frequency=277:duration=12:sample_rate=44100",
         "-filter_complex", "[0][1]amix=inputs=2,volume=0.05,aformat=channel_layouts=stereo", str(ruta)],
        check=True,
    )
    return ruta


# --- Volumen y MP3 (solo ffmpeg) -------------------------------------------

@pytest.mark.parametrize("masterizacion", [True, False], ids=["masterizada", "anterior"])
def test_normaliza_al_loudness_objetivo_y_codifica_mp3(wav_bajito, tmp_path, config, masterizacion):
    config = config.model_copy(update={"render_masterizacion": masterizacion})
    mp3 = tmp_path / "cancion.mp3"

    lufs, pico = normalizar_y_codificar(wav_bajito, mp3, duracion_musica=9.0, config=config,
                                        metadatos={"title": "prueba"})

    assert mp3.is_file()
    assert lufs == pytest.approx(config.render_lufs_objetivo, abs=1.0)
    assert pico <= config.render_pico_maximo_dbtp + 0.5
    # Medición independiente, con otro medidor (loudnorm) sobre el MP3 ya escrito.
    lufs_independiente, pico_independiente = _medir_lufs(mp3)
    assert lufs_independiente == pytest.approx(config.render_lufs_objetivo, abs=1.0)
    assert pico_independiente <= config.render_pico_maximo_dbtp + 0.5


def test_recorta_la_cola_y_hace_fade(wav_bajito, tmp_path, config):
    mp3 = tmp_path / "cancion.mp3"
    normalizar_y_codificar(wav_bajito, mp3, duracion_musica=9.0, config=config)

    # 9 s de música + 2.5 s de cola (con margen por el relleno del MP3).
    assert duracion_audio(mp3) == pytest.approx(9.0 + config.render_cola_segundos, abs=0.15)


# --- Herramientas faltantes: error claro ------------------------------------

def test_fluidsynth_configurado_que_no_existe_da_error_claro(tmp_path):
    config = Configuracion(fluidsynth=str(tmp_path / "no-existe.exe"))
    with pytest.raises(ErrorRender, match="configuración del servidor"):
        resolver_fluidsynth(config)


def test_sin_fluidsynth_en_ningun_lado_da_error_que_no_culpa_al_tarareo(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pipeline.render.shutil.which", lambda _nombre: None)
    config = Configuracion(directorio_herramientas=tmp_path)

    with pytest.raises(ErrorRender) as info:
        resolver_fluidsynth(config)

    assert "no del tarareo" in info.value.mensaje


def test_soundfont_configurado_que_no_existe_da_error(tmp_path):
    config = Configuracion(soundfont=tmp_path / "no-existe.sf2")
    with pytest.raises(ErrorRender, match="SoundFont"):
        resolver_soundfont(config)


# --- Mezcla del MIDI ---------------------------------------------------------

def _arreglo_de_prueba(config, preset="pop"):
    frase = [(60, 1), (64, 1), (67, 2), (65, 1), (69, 1), (72, 2), (67, 1), (71, 1), (74, 2), (72, 4)]
    notas, t = [], 0.5
    for nota, dur in frase:
        notas.append(NotaMusical(nota=nota, inicio=t, duracion=dur * 0.6 * 0.92, velocidad=90))
        t += dur * 0.6
    analisis = analizar(notas, None, config)
    armonia = armonizar(analisis.melodiaCuantizada, analisis.tonalidad)
    estilo = inferir_estilo(notas, analisis).model_copy(update={"preset": preset})
    return arreglar(analisis, armonia, estilo)


def test_el_midi_lleva_la_mezcla_melodia_adelante_colchon_atras(tmp_path, config):
    resultado = _arreglo_de_prueba(config)
    ruta = tmp_path / "arreglo.mid"
    escribir_arreglo_midi(resultado, ruta)

    midi = pretty_midi.PrettyMIDI(str(ruta))
    volumen = {}
    for instrumento, pista in zip(midi.instruments, resultado.arreglo.pistas, strict=True):
        cc7 = [c.value for c in instrumento.control_changes if c.number == 7]
        assert cc7 == [MEZCLA_POR_ROL[pista.rol][0]]
        volumen[pista.rol] = cc7[0]
    assert volumen["melodia"] > volumen["segunda"] > volumen["colchon"]


# --- Render completo (necesita FluidSynth) ------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("preset", ["pop", "epico", "electronico"])
def test_render_completo_da_un_mp3_de_la_cancion(tmp_path, config, requiere_render, preset):
    resultado = _arreglo_de_prueba(config, preset)
    ruta_midi = tmp_path / "arreglo.mid"
    escribir_arreglo_midi(resultado, ruta_midi)

    ruta_mp3, resumen = renderizar(ruta_midi, tmp_path, resultado.arreglo.duracionSegundos, config)

    assert ruta_mp3.name == "cancion.mp3"
    assert not (tmp_path / "render-cancion.wav").exists()  # el intermedio pesado se borra
    esperado = resultado.arreglo.duracionSegundos + config.render_cola_segundos
    assert resumen.duracionSegundos == pytest.approx(esperado, abs=0.2)
    assert resumen.loudnessLufs == pytest.approx(config.render_lufs_objetivo, abs=1.0)
    assert resumen.licenciaSoundfont.startswith("MIT")
    assert resumen.masterizacion == "suave-v1"


def test_el_limitador_frena_los_picos_cuando_la_ganancia_los_pasaria(tmp_path, config):
    """Audio casi en silencio con un golpe fuerte: al subir el volumen, el golpe no puede pasar de -1 dBTP."""
    wav = tmp_path / "golpe.wav"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=220:duration=10:sample_rate=44100",
         "-af", "volume='if(between(t,5,5.05),0.9,0.02)':eval=frame,aformat=channel_layouts=stereo", str(wav)],
        check=True,
    )
    mp3 = tmp_path / "cancion.mp3"

    _, pico = normalizar_y_codificar(wav, mp3, duracion_musica=8.0, config=config)

    assert pico <= config.render_pico_maximo_dbtp + 0.5
    assert _medir_lufs(mp3)[1] <= config.render_pico_maximo_dbtp + 0.5
