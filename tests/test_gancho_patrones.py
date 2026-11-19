
from itertools import pairwise

import pytest

from app.modelos import NotaCuantizada
from app.pipeline.arreglo import ESTILOS, arreglar
from app.pipeline.gancho import detectar_gancho
from app.pipeline.patrones import adaptar_acompanamiento, variar_patrones
from tests.test_arreglo import _entrada


def _notas(alturas):
    return [NotaCuantizada(nota=n, inicioPulsos=i, duracionPulsos=0.8, velocidad=85, ajustada=True)
            for i, n in enumerate(alturas)]


def test_detecta_un_gancho_repetido_y_transpuesto():
    g = detectar_gancho(_notas([60, 62, 64, 60, 65, 67, 69, 65]))
    assert g.repetido and g.confianza >= 0.85 and g.inicioPulsos == 0
    assert g.duracionPulsos == 4


def test_no_inventa_repeticion_si_la_frase_no_se_repite():
    g = detectar_gancho(_notas([60, 67, 61, 72, 63, 68, 59]))
    assert not g.repetido and g.confianza == 0
    assert "Propuesta" in g.motivo


@pytest.mark.parametrize("preset", list(ESTILOS))
def test_tres_familias_ritmicas_por_estilo_sin_mutar_las_tablas(preset):
    original = ESTILOS[preset]
    familias = [variar_patrones(original, h) for h in (0, 13, 26)]
    assert len({n for _, n in familias}) == 3
    assert all(e.variantes == original.variantes for e, _ in familias)
    assert familias[0][0] == original
    assert len({repr((e.bateria, e.bajo)) for e, _ in familias}) == 3
    assert adaptar_acompanamiento(((0, 1, "acorde"), (2, 1, "acorde")), "impulso")[-1][0] == 3.5


@pytest.mark.parametrize("preset", list(ESTILOS))
def test_estructura_con_estribillo_conserva_el_verso_y_repite_el_gancho(config, preset):
    frase = [(60, 1), (62, 1), (64, 1), (60, 1), (65, 1), (67, 1), (69, 1), (65, 1)]
    entrada = _entrada(config, preset, frase)
    base = arreglar(*entrada)
    nuevo = arreglar(*entrada, con_estribillo=True, variedad_ritmica=True)
    assert nuevo.arreglo.gancho.repetido
    assert {s.funcion for s in nuevo.arreglo.estructura} >= {"verso", "estribillo final"}
    assert 60 <= nuevo.arreglo.duracionSegundos <= 90
    verso = next(s for s in nuevo.arreglo.estructura if s.funcion == "verso")
    a, b = verso.compasInicio*4, (verso.compasInicio+verso.compases)*4
    assert [(e.nota, e.inicio) for e in nuevo.eventos if e.pista == "melodia" and a <= e.inicio < b] == [
        (e.nota, e.inicio) for e in base.eventos if e.pista == "melodia" and a <= e.inicio < b]
    assert nuevo.eventos == arreglar(*entrada, con_estribillo=True, variedad_ritmica=True).eventos
    melodia = sorted((e for e in nuevo.eventos if e.pista == "melodia"), key=lambda e: e.inicio)
    assert all(e.inicio+e.duracion <= f.inicio+1e-5 for e, f in pairwise(melodia))
    assert any(e.origenPulsos is not None for e in melodia)
