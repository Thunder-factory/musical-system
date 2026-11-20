from types import SimpleNamespace

import pytest
from music21 import converter, harmony, note

from app.modelos import NotaCuantizada
from app.pipeline.partitura import escribir_partitura


@pytest.mark.parametrize("tonalidad", ["C major", "Bb minor", "F# major"])
def test_musicxml_se_reabre_con_notas_silencios_y_acordes(tmp_path, tonalidad):
    notas = [NotaCuantizada(nota=p, inicioPulsos=i, duracionPulsos=d, velocidad=85, ajustada=True)
             for p, i, d in [(60, 0, 1), (64, 1.5, 1.5), (67, 3, 3), (60, 6, 2)]]
    analisis = SimpleNamespace(tonalidad=tonalidad, compas="4/4", bpm=96, melodiaCuantizada=notas)
    acordes = SimpleNamespace(progresion=[SimpleNamespace(notas=[60, 64, 67], inicioPulsos=0),
                                         SimpleNamespace(notas=[65, 68, 72], inicioPulsos=4)])
    ruta = tmp_path / "partitura.musicxml"
    escribir_partitura(analisis, acordes, ruta)

    abierta = converter.parse(str(ruta))
    melodicas = list(abierta.parts[0].stripTies().recurse().getElementsByClass(note.Note))
    assert [n.pitch.midi for n in melodicas] == [60, 64, 67, 60]
    assert [n.quarterLength for n in melodicas] == [1, 1.5, 3, 2]
    assert list(abierta.recurse().getElementsByClass(note.Rest))
    assert len(list(abierta.recurse().getElementsByClass(harmony.ChordSymbol))) == 2
