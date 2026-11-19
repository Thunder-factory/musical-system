"""
Tests de la etapa 6.5 (estilo inferido).

Cada estilo se prueba con rasgos típicos de un tarareo que "suena" a ese
estilo. El usuario nunca elige: el estilo sale solo de los rasgos.
"""

import pytest

from app.modelos import NotaMusical, RasgosTarareo
from app.pipeline import estilo as modulo_estilo
from app.pipeline.estilo import (
    PERFILES,
    elegir_estilo,
    medir_articulacion,
    medir_repeticion,
)


def rasgos(**valores) -> RasgosTarareo:
    base = {"bpm": 100.0, "modo": "mayor", "densidad": 1.0, "articulacion": 0.85, "rango": 9, "saltos": 0.3}
    return RasgosTarareo(**(base | valores))


@pytest.mark.parametrize("esperado, valores", [
    ("balada", {"bpm": 68, "densidad": 0.6, "articulacion": 0.92, "rango": 10, "saltos": 0.35}),
    ("pop", {"bpm": 108, "densidad": 1.2, "articulacion": 0.8, "rango": 10, "saltos": 0.35}),
    ("rock_suave", {"bpm": 128, "modo": "menor", "densidad": 1.5, "articulacion": 0.55,
                    "rango": 14, "saltos": 0.6}),
    ("lofi", {"bpm": 78, "densidad": 1.2, "articulacion": 0.85, "rango": 6, "saltos": 0.25}),
    ("folk", {"bpm": 100, "densidad": 1.1, "articulacion": 0.85, "rango": 9, "saltos": 0.1}),
    ("epico", {"bpm": 72, "modo": "menor", "densidad": 0.7, "articulacion": 0.9, "rango": 17, "saltos": 0.4}),
    ("electronico", {"bpm": 124, "densidad": 1.6, "articulacion": 0.5, "rango": 7, "saltos": 0.3,
                     "repeticion": 0.8}),
])
def test_cada_estilo_sale_de_sus_rasgos_tipicos(esperado, valores):
    assert elegir_estilo(rasgos(**valores)).preset == esperado


def test_hay_siete_estilos_y_todos_son_alcanzables():
    assert set(PERFILES) == {"balada", "pop", "rock_suave", "lofi", "folk", "epico", "electronico"}


def test_el_motivo_explica_con_los_rasgos_que_mas_pesaron():
    resultado = elegir_estilo(rasgos(bpm=68, densidad=0.6, articulacion=0.92, rango=10, saltos=0.35))

    assert "68 BPM (lento)" in resultado.motivo
    assert "ligadas" in resultado.motivo
    assert next(iter(resultado.puntajes)) == "balada"  # ordenados de mayor a menor


def test_el_motivo_no_nombra_rasgos_que_contradicen_al_estilo():
    """Una balada con notas algo cortadas: el motivo no dice 'balada porque notas cortadas'."""
    resultado = elegir_estilo(rasgos(bpm=62, densidad=1.0, articulacion=0.65, rango=5, saltos=0.12))

    assert resultado.preset in ("balada", "lofi")
    assert "cortadas" not in resultado.motivo


def test_el_mismo_tarareo_da_siempre_el_mismo_estilo():
    r = rasgos(bpm=93, densidad=1.1, articulacion=0.7, rango=11, saltos=0.45)
    assert len({elegir_estilo(r).preset for _ in range(10)}) == 1


def test_en_empate_practico_gana_el_mas_neutro(monkeypatch):
    monkeypatch.setattr(modulo_estilo, "puntuar", lambda _r: {
        "epico": (0.80, [(1.0, "rango", 1.0)]),
        "pop": (0.79, [(1.0, "bpm", 1.0)]),
        "balada": (0.50, [(1.0, "bpm", 1.0)]),
    })

    resultado = elegir_estilo(rasgos())

    assert resultado.preset == "pop"
    assert "empate práctico con epico" in resultado.motivo


# --- Medición de rasgos ----------------------------------------------------

def _notas(fraccion_sostenida: float, iois: list[float]) -> list[NotaMusical]:
    notas, inicio = [], 0.0
    for ioi in iois:
        notas.append(NotaMusical(nota=60, inicio=inicio, duracion=ioi * fraccion_sostenida, velocidad=80))
        inicio += ioi
    return notas


def test_articulacion_ligada_y_cortada():
    assert medir_articulacion(_notas(0.95, [0.5] * 8)) == pytest.approx(0.95)
    assert medir_articulacion(_notas(0.4, [0.5] * 8)) == pytest.approx(0.4)


def test_la_pausa_entre_frases_no_cuenta_como_staccato():
    """Una nota ligada seguida de 4 s de respiración sigue siendo ligada."""
    notas = _notas(0.95, [0.5, 0.5, 0.5, 4.0, 0.5, 0.5, 0.5])
    notas[3] = notas[3].model_copy(update={"duracion": 0.45})  # sostiene 0.45 s y después respira
    assert medir_articulacion(notas) > 0.9


# --- Repetición y estilo electrónico ----------------------------------------

def test_repeticion_detecta_un_motivo_repetido_aunque_este_transpuesto():
    motivo = [60, 62, 64, 60]
    repetido = motivo * 4
    transpuesto = [n + t for t in (0, 5, 7, 0) for n in motivo]

    assert medir_repeticion(repetido) == pytest.approx(1.0)
    assert medir_repeticion(transpuesto) > 0.25
    assert medir_repeticion([60, 67, 62, 71, 59, 64, 69, 61, 66]) == 0.0  # sin figuras repetidas


def test_un_tarareo_rapido_sin_repeticion_no_es_electronico():
    """Lo que define al electrónico es el loop: sin repetición, un tarareo rápido es pop o rock."""
    r = rasgos(bpm=124, densidad=1.6, articulacion=0.5, rango=7, saltos=0.3, repeticion=0.1)
    assert elegir_estilo(r).preset != "electronico"


# --- Confianza y mensaje -----------------------------------------------------

def test_estilo_claro_tiene_confianza_alta_y_no_es_ambiguo():
    resultado = elegir_estilo(rasgos(bpm=124, densidad=1.6, articulacion=0.5, rango=7, saltos=0.3,
                                     repeticion=0.8))
    assert resultado.preset == "electronico"
    # Por encima del umbral de ambigüedad (margen 0.08 sobre 0.25 = 0.32).
    assert resultado.confianza > modulo_estilo.MARGEN_AMBIGUO / modulo_estilo.MARGEN_CONFIANZA_TOTAL
    assert resultado.ambiguo is False
    assert resultado.mensaje == "Tu tarareo suena a electrónico."


def test_estilo_parejo_entre_dos_se_marca_ambiguo_con_mensaje_para_el_usuario():
    """El caso de 03 T del lote: balada 0.874 contra lo-fi 0.867."""
    resultado = elegir_estilo(rasgos(bpm=62, densidad=1.0, articulacion=0.72, rango=5, saltos=0.12))

    assert resultado.ambiguo is True
    assert resultado.confianza < 0.3
    assert {resultado.preset, resultado.alternativa} == {"balada", "lofi"}
    assert "suena entre" in resultado.mensaje


# --- Calibración: tarareos reales validados de oído ---------------------------

def _validados():
    import csv
    from pathlib import Path

    ruta = Path(__file__).resolve().parent / "audio" / "estilos_validados.csv"
    lineas = [linea for linea in ruta.read_text(encoding="utf-8").splitlines() if not linea.startswith("#")]
    return list(csv.DictReader(lineas))


@pytest.mark.parametrize("fila", _validados(), ids=lambda f: f["archivo"])
def test_los_tarareos_validados_conservan_su_estilo(fila):
    """
    Regresión de calibración: cualquier cambio en los perfiles (un estilo nuevo,
    un umbral) no puede cambiarle el estilo a un tarareo que alguien ya validó.
    """
    rasgos_reales = RasgosTarareo(
        bpm=float(fila["bpm"]), modo=fila["modo"], densidad=float(fila["densidad"]),
        articulacion=float(fila["articulacion"]), rango=int(fila["rango"]),
        saltos=float(fila["saltos"]), repeticion=float(fila["repeticion"]),
    )
    assert elegir_estilo(rasgos_reales).preset == fila["preset"]


# --- Versiones alternativas ---------------------------------------------------

def test_propone_como_alternativas_los_otros_estilos_que_encajan():
    """mi_tarareo (validado): lo-fi principal; balada y épico también encajan (≥ 0.6)."""
    resultado = elegir_estilo(rasgos(bpm=64, modo="menor", densidad=0.986, articulacion=0.616, rango=7,
                                     saltos=0.294, repeticion=0.0))
    assert resultado.preset == "lofi"
    assert resultado.alternativas == ["balada", "epico"]
    assert all(resultado.puntajes[a] >= modulo_estilo.UMBRAL_ALTERNATIVA for a in resultado.alternativas)


def test_nunca_propone_un_estilo_que_no_encaja():
    resultado = elegir_estilo(rasgos(bpm=124, densidad=1.6, articulacion=0.5, rango=7, saltos=0.3, repeticion=0.8))
    assert len(resultado.alternativas) <= modulo_estilo.MAXIMO_ALTERNATIVAS
    assert resultado.preset not in resultado.alternativas
    assert all(resultado.puntajes[a] >= modulo_estilo.UMBRAL_ALTERNATIVA for a in resultado.alternativas)
