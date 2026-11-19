from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pretty_midi

from app.modelos import NotaCuantizada, NotaMusical, PuntoExpresion
from app.pipeline.expresion import conservar_expresion, expresar_arreglo
from app.pipeline.melodia import NotaCruda
from app.pipeline.salida import escribir_arreglo_midi
from tests.test_render import _arreglo_de_prueba


def test_conserva_variaciones_sin_copiar_desafinado_constante():
    nota = NotaMusical(nota=60, inicio=0, duracion=1, velocidad=90)
    curva = tuple(1.0 + 0.4 * np.sin(np.arange(90) * 0.4))
    conservar_expresion([nota], [NotaCruda(60, 0, 1, 0.8, curva)])
    assert len(nota.expresion) <= 34
    assert max(abs(p.semitonos) for p in nota.expresion) <= 0.35
    assert any(abs(p.semitonos) > 0.05 for p in nota.expresion)
    assert nota.expresion[0].semitonos == nota.expresion[-1].semitonos == 0
    conservar_expresion([nota], [NotaCruda(60, 0, 1, 0.8, (1.0,) * 50)])
    assert all(p.semitonos == 0 for p in nota.expresion)


def test_expresion_no_cambia_notas_y_se_limita_a_la_pista_principal(tmp_path, config):
    resultado = _arreglo_de_prueba(config)
    next(p for p in resultado.arreglo.pistas if p.rol == "melodia").programa = 49
    inicio_a = next(s.compasInicio * 4 for s in resultado.arreglo.estructura if s.nombre == "A")
    notas = [NotaCuantizada(nota=e.nota, inicioPulsos=e.inicio-inicio_a, duracionPulsos=e.duracion,
                            velocidad=e.velocidad, ajustada=True, expresion=[
                                PuntoExpresion(posicion=0, semitonos=0),
                                PuntoExpresion(posicion=0.5, semitonos=0.25),
                                PuntoExpresion(posicion=1, semitonos=0),
                            ]) for e in resultado.eventos
             if e.pista == "melodia" and inicio_a <= e.inicio < inicio_a + 4]
    expresivo = expresar_arreglo(resultado, SimpleNamespace(melodiaCuantizada=notas),
                                  SimpleNamespace(anacrusaPulsos=0))
    assert [replace(e, expresion=()) for e in expresivo.eventos] == resultado.eventos
    assert any(e.expresion for e in expresivo.eventos)
    ruta = tmp_path / "arreglo.mid"
    escribir_arreglo_midi(expresivo, ruta)
    midi = pretty_midi.PrettyMIDI(str(ruta))
    principal = next(p for p in midi.instruments if p.name == "Melodía")
    assert principal.pitch_bends and max(abs(b.pitch) for b in principal.pitch_bends) <= 1434
    assert principal.pitch_bends[-1].pitch == 0
    assert all(not p.pitch_bends for p in midi.instruments if p.name != "Melodía")
    next(p for p in resultado.arreglo.pistas if p.rol == "melodia").programa = 0
    assert expresar_arreglo(resultado, SimpleNamespace(melodiaCuantizada=notas),
                             SimpleNamespace(anacrusaPulsos=0)) == resultado
