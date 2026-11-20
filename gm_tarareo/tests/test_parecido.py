"""Parecido entre la melodía del arreglo y un audio con IA (app/pipeline/parecido.py)."""

from pathlib import Path

import numpy as np
import pretty_midi
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.pipeline.parecido import clases_sonando, nivel, notas_melodia, puntaje

MELODIA = [(60, 0.0, 0.5), (62, 0.5, 1.0), (64, 1.0, 1.5), (65, 1.5, 2.0), (67, 2.0, 3.0),
           (65, 3.0, 3.5), (64, 3.5, 4.0), (62, 4.0, 4.5), (60, 4.5, 6.0)]


def test_misma_melodia_puntua_alto_y_otra_bajo():
    exacta = clases_sonando([(i, f, n) for n, i, f in MELODIA], 7)
    otra = clases_sonando([(i, f, n + 6) for n, i, f in MELODIA], 7)  # todo un tritono arriba
    assert puntaje(MELODIA, exacta) > 0.8
    assert puntaje(MELODIA, otra) < 0.1


def test_audio_que_suena_todo_no_gana_por_azar():
    todo = clases_sonando([(0, 7, n) for n in range(60, 72)], 7)
    assert puntaje(MELODIA, todo) == 0


def test_niveles():
    assert (nivel(0.45), nivel(0.25), nivel(0.05)) == ("alto", "medio", "bajo")


def _midi(ruta: Path, notas, nombre="Melodía") -> Path:
    midi = pretty_midi.PrettyMIDI()
    pista = pretty_midi.Instrument(program=0, name=nombre)
    pista.notes = [pretty_midi.Note(velocity=100, pitch=n, start=i, end=f) for n, i, f in notas]
    midi.instruments.append(pista)
    midi.write(str(ruta))
    return ruta


def _sintetizar(ruta: Path, notas, sr=22050) -> Path:
    audio = np.zeros(int(sr * (notas[-1][2] + 0.5)), dtype=np.float32)
    for nota, inicio, fin in notas:
        t = np.arange(int((fin - inicio) * sr)) / sr
        frecuencia = 440 * 2 ** ((nota - 69) / 12)
        tono = sum(np.sin(2 * np.pi * frecuencia * k * t) / k for k in (1, 2, 3))
        envolvente = np.minimum(1, np.minimum(t / 0.02, (fin - inicio - t) / 0.05))
        a = int(inicio * sr)
        audio[a:a + len(t)] += 0.3 * tono * envolvente
    sf.write(ruta, audio, sr)
    return ruta


def test_notas_melodia_exige_la_pista(tmp_path):
    with pytest.raises(ValueError):
        notas_melodia(_midi(tmp_path / "x.mid", MELODIA, nombre="Bajo"))


@pytest.mark.slow
def test_endpoint_mide_cada_audio_con_basic_pitch(tmp_path):
    from app.main import app

    arreglo = _midi(tmp_path / "arreglo.mid", MELODIA)
    igual = _sintetizar(tmp_path / "igual.wav", MELODIA)
    distinta = _sintetizar(tmp_path / "distinta.wav", [(n + 6, i, f) for n, i, f in MELODIA])

    with TestClient(app) as client:
        respuesta = client.post("/parecido", json={
            "arregloUrl": str(arreglo), "audioUrls": [str(igual), str(distinta), str(tmp_path / "no-existe.wav")],
        })

    assert respuesta.status_code == 200
    igual_r, distinta_r, falta_r = respuesta.json()["resultados"]
    assert igual_r["puntaje"] > 0.8 and igual_r["nivel"] == "alto"
    assert distinta_r["puntaje"] < 0.15 and distinta_r["nivel"] == "bajo"
    assert falta_r == {"puntaje": None, "nivel": None}
