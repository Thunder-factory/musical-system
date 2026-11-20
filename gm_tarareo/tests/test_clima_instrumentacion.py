"""Reglas musicales, claridad del arreglo y exportación de los siete estilos."""

from itertools import product

import pretty_midi
import pytest

from app.modelos import ClimaMusical, RasgosTarareo
from app.pipeline.arreglo import ESTILOS, arreglar
from app.pipeline.clima import inferir_clima
from app.pipeline.salida import MEZCLA_POR_ROL, escribir_arreglo_midi
from app.versiones import identificador_version
from tests.test_arreglo import _entrada, _variantes


@pytest.mark.parametrize("nombre,bpm,modo,densidad,rango,saltos,articulacion", [
    ("sereno", 64, "mayor", 0.5, 4, 0.1, 0.9),
    ("melancolico", 72, "menor", 0.6, 6, 0.1, 0.9),
    ("luminoso", 100, "mayor", 1.2, 10, 0.3, 0.6),
    ("energico", 140, "menor", 1.8, 14, 0.5, 0.3),
    ("intenso", 160, "menor", 2.2, 18, 0.9, 0.8),
])
def test_clima_combina_rasgos_y_no_confunde_menor_con_tristeza(
        nombre, bpm, modo, densidad, rango, saltos, articulacion):
    rasgos = RasgosTarareo(bpm=bpm, modo=modo, densidad=densidad,
                          rango=rango, saltos=saltos, articulacion=articulacion)
    clima = inferir_clima(rasgos)
    assert clima.nombre == nombre
    assert clima == inferir_clima(rasgos)
    assert str(bpm) in clima.motivo and modo in clima.motivo


CLIMAS = [ClimaMusical(nombre=n, intensidad=i, confianza=0.6, ambiguo=False, motivo="Ejemplo musical")
          for n, i in [("sereno", .2), ("melancolico", .3), ("luminoso", .5),
                       ("energico", .75), ("intenso", .9)]]


@pytest.mark.parametrize("preset,clima", product(ESTILOS, CLIMAS))
def test_capas_respetan_melodia_duracion_y_espacio(config, preset, clima):
    entrada = _entrada(config, preset)
    original = ESTILOS[preset]
    base = arreglar(*entrada, con_estribillo=True)
    nuevo = arreglar(*entrada, con_estribillo=True, clima=clima, instrumentacion_ampliada=True)
    assert nuevo.arreglo.clima == clima
    assert 60 <= nuevo.arreglo.duracionSegundos <= 90
    assert [(e.nota, e.inicio, e.duracion) for e in nuevo.eventos if e.pista == "melodia"] == [
        (e.nota, e.inicio, e.duracion) for e in base.eventos if e.pista == "melodia"]
    assert nuevo == arreglar(*entrada, con_estribillo=True, clima=clima, instrumentacion_ampliada=True)
    assert ESTILOS[preset] == original
    assert {p.rol for p in nuevo.arreglo.pistas} >= {"color1", "color2"}
    # Contar también la segunda voz: nunca más de dos apoyos simultáneos.
    apoyos = [e for e in nuevo.eventos if e.pista in ("segunda", "colchon", "color1", "color2")]
    for t in {e.inicio for e in apoyos}:
        activos = {e.pista for e in apoyos if e.inicio <= t < e.inicio + e.duracion - 1e-5}
        assert len(activos) <= 2
    verso = next(s for s in nuevo.arreglo.estructura if s.nombre == "A")
    assert not any(e.pista == "color1" and verso.compasInicio*4 <= e.inicio <
                   (verso.compasInicio+verso.compases)*4 for e in nuevo.eventos)


@pytest.mark.parametrize("preset,variante", _variantes())
def test_instrumentacion_exporta_midi_valido_con_mezcla_subordinada(config, tmp_path, preset, variante):
    entrada = _entrada(config, preset)
    resultado = arreglar(*entrada, variante=variante, clima=inferir_clima(entrada[2].rasgos),
                         instrumentacion_ampliada=True)
    ruta = tmp_path / "instrumentos.mid"
    escribir_arreglo_midi(resultado, ruta)
    midi = pretty_midi.PrettyMIDI(str(ruta))
    assert len(midi.instruments) == len(resultado.arreglo.pistas) < 10
    for pista, instrumento in zip(resultado.arreglo.pistas, midi.instruments, strict=True):
        assert instrumento.notes and instrumento.program == pista.programa
        assert all(0 <= n.pitch <= 127 and n.end > n.start for n in instrumento.notes)
        if pista.rol.startswith("color"):
            volumen = next(c.value for c in instrumento.control_changes if c.number == 7)
            assert volumen == MEZCLA_POR_ROL[pista.rol][0] < MEZCLA_POR_ROL["acompanamiento"][0]


def test_clima_solo_modifica_intensidad_del_apoyo(config):
    entrada = _entrada(config, "pop")
    suave = arreglar(*entrada, clima=CLIMAS[0])
    fuerte = arreglar(*entrada, clima=CLIMAS[-1])
    assert [e for e in suave.eventos if e.pista == "melodia"] == [
        e for e in fuerte.eventos if e.pista == "melodia"]
    assert sum(e.velocidad for e in suave.eventos if e.pista == "bateria") < sum(
        e.velocidad for e in fuerte.eventos if e.pista == "bateria")


def test_confianza_baja_se_explica_como_ambiguedad():
    rasgos = RasgosTarareo(bpm=85, modo="mayor", densidad=1, rango=8, saltos=.2, articulacion=.75)
    clima = inferir_clima(rasgos)
    assert clima.ambiguo and clima.confianza < .25
    assert "También encaja" in clima.motivo


def test_ajustes_musicales_invalidan_la_cache_de_completas(config):
    from uuid import uuid4

    origen = uuid4()
    base = identificador_version(origen, 1, config)
    for opcion in ("arreglo_clima_musical", "arreglo_instrumentacion_ampliada"):
        assert identificador_version(origen, 1, config.model_copy(update={opcion: False})) != base
