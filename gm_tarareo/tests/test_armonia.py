"""
Tests de la etapa 6 (armonía) con melodías sintéticas en pulsos.

Cada melodía se escribe compás por compás: (nota MIDI, duración en pulsos).
Los acordes esperados son los que contienen las notas que se cantaron.
"""

import pytest

from app.modelos import NotaCuantizada
from app.pipeline.armonia import (
    armonizar,
    elegir_anacrusa,
    leer_tonalidad,
    nombre_acorde,
)

C4, D4, E4, F4, Fs4, G4, Gs4, A4, B4 = 60, 62, 64, 65, 66, 67, 68, 69, 71
C5, D5, E5 = 72, 74, 76


def melodia(*notas_y_duraciones: tuple[int, float], inicio: float = 0.0) -> list[NotaCuantizada]:
    resultado, posicion = [], inicio
    for nota, duracion in notas_y_duraciones:
        resultado.append(NotaCuantizada(nota=nota, inicioPulsos=posicion, duracionPulsos=duracion,
                                        velocidad=90, ajustada=True))
        posicion += duracion
    return resultado


# --- Tonalidad y nombres ---------------------------------------------------

@pytest.mark.parametrize("tonalidad, esperado", [
    ("C major", (0, "mayor")), ("G major", (7, "mayor")), ("Bb minor", (10, "menor")),
    ("F# minor", (6, "menor")), ("Eb major", (3, "mayor")),
])
def test_leer_tonalidad(tonalidad, esperado):
    assert leer_tonalidad(tonalidad) == esperado


def test_nombres_de_acordes_con_sostenidos_y_bemoles():
    assert nombre_acorde(6, "menor", bemoles=False) == "F#m"
    assert nombre_acorde(10, "mayor", bemoles=True) == "Bb"


def test_tonalidad_con_bemoles_escribe_los_acordes_con_bemoles():
    # Fa mayor: el IV es Bb, no A#.
    notas = melodia((F4, 2), (A4, 2), (B4 - 1, 2), (D5, 2), (C5, 2), (E4, 2), (F4, 4))
    assert "Bb" in armonizar(notas, "F major").acordes


# --- Elegir acordes que contienen la melodía ----------------------------------

def test_cada_compas_recibe_el_acorde_que_contiene_sus_notas():
    notas = melodia(
        (C4, 1), (E4, 1), (G4, 2),      # Do-Mi-Sol → C
        (F4, 1), (A4, 1), (C5, 2),      # Fa-La-Do → F
        (G4, 1), (B4, 1), (D5, 2),      # Sol-Si-Re → G
        (C5, 4),                        # Do → C (cierre)
    )
    resultado = armonizar(notas, "C major")

    assert resultado.acordes == ["C", "F", "G", "C"]
    assert [a.grado for a in resultado.progresion] == ["I", "IV", "V", "I"]
    assert all(a.cobertura == 1.0 for a in resultado.progresion)


def test_una_nota_corta_de_paso_no_cambia_el_acorde():
    """Un Re de un cuarto de pulso entre Do y Mi es de paso: el compás sigue siendo C."""
    notas = melodia((C4, 1.75), (D4, 0.25), (E4, 2), (F4, 2), (A4, 2), (C4, 4))
    assert armonizar(notas, "C major").acordes[0] == "C"


def test_en_menor_el_cierre_usa_el_v_mayor_si_se_canta_la_sensible():
    notas = melodia(
        (A4, 1), (C5, 1), (E5, 2),      # Am
        (D4, 1), (F4, 1), (A4, 2),      # Dm
        (E4, 1), (Gs4, 1), (B4, 2),     # E (con Sol#)
        (A4, 4),                        # Am
    )
    resultado = armonizar(notas, "A minor")

    assert resultado.acordes == ["Am", "Dm", "E", "Am"]
    assert resultado.progresion[2].grado == "V"


def test_termina_en_la_tonica_cuando_la_melodia_lo_permite():
    """Un Mi final cabe en C, Em y Am: el cierre elige la tónica."""
    notas = melodia((C4, 2), (E4, 2), (F4, 2), (A4, 2), (G4, 2), (D4, 2), (E4, 4))
    assert armonizar(notas, "C major").acordes[-1] == "C"


def test_no_repite_el_mismo_acorde_cuatro_compases_si_hay_alternativas():
    """Un Sol sostenido 4 compases cabe en C, Em y G: la progresión no se estanca."""
    notas = melodia((G4, 4), (G4, 4), (G4, 4), (G4, 4))
    acordes = armonizar(notas, "C major").acordes
    assert len(set(acordes)) >= 2


def test_un_compas_con_dos_armonias_se_divide_en_dos_acordes():
    """Fa-La y después Sol-Si: ninguna tríada cubre el compás entero (IV → V)."""
    notas = melodia((F4, 1), (A4, 1), (G4, 1), (B4, 1), (C5, 4))
    resultado = armonizar(notas, "C major")

    primer_compas = [a for a in resultado.progresion if a.compas == 0]
    assert [a.nombre for a in primer_compas] == ["F", "G"]
    assert [a.duracionPulsos for a in primer_compas] == [2, 2]


# --- Anacrusa y tiempos ----------------------------------------------------

def test_detecta_una_nota_de_entrada_antes_del_primer_tiempo():
    """Sol de entrada (1 pulso) y después Do largo: el Do es el tiempo 1."""
    notas = melodia((G4, 1), (C5, 4), (E5, 2), (D5, 2), (C5, 4))
    assert elegir_anacrusa(notas) == 3


def test_sin_evidencia_no_inventa_anacrusa():
    notas = melodia((C4, 1), (D4, 1), (E4, 1), (F4, 1), (G4, 4))
    assert elegir_anacrusa(notas) == 0


def test_la_progresion_cubre_toda_la_melodia_sin_huecos():
    notas = melodia((G4, 1), (C5, 4), (E5, 2), (D5, 2), (C5, 3))
    resultado = armonizar(notas, "C major")

    assert resultado.progresion[0].inicioPulsos == 0
    for actual, siguiente in zip(resultado.progresion, resultado.progresion[1:], strict=False):
        assert actual.inicioPulsos + actual.duracionPulsos == pytest.approx(siguiente.inicioPulsos)
    final = resultado.progresion[-1]
    assert final.inicioPulsos + final.duracionPulsos >= notas[-1].inicioPulsos + notas[-1].duracionPulsos
