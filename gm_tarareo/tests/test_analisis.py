"""
Tests de la etapa 5 (análisis musical) con melodías sintéticas.

La referencia no es "qué canción era" (el sistema no identifica canciones),
sino melodías construidas con un tempo y una tonalidad conocidos, con
desprolijidad rítmica como la de un tarareo real (±20 ms).
"""

import numpy as np
import pretty_midi
import pytest

from app.modelos import MotivoFallo, NotaMusical
from app.pipeline.analisis import (
    analizar,
    estimar_bpm,
    estimar_tonalidad,
    regularizar,
    tempo_por_densidad,
)
from app.pipeline.excepciones import ErrorAudioInvalido
from app.pipeline.salida import escribir_midi

# Duraciones en pulsos (negras) de frases típicas de un tarareo.
NEGRAS_Y_CORCHEAS = [1, 0.5, 0.5, 1, 1, 0.5, 0.5, 2, 1, 0.5, 0.5, 1, 1, 2]
CON_BLANCAS = [1, 1, 2, 0.5, 0.5, 1, 2, 1, 1, 1, 1, 2, 2]
CON_PUNTILLO = [1.5, 0.5, 1, 1, 1.5, 0.5, 2, 1.5, 0.5, 1, 1, 2]
SOLO_CORCHEAS = [0.5] * 8 + [1, 1, 0.5, 0.5, 1, 2]

DO_MAYOR = [60, 62, 64, 65, 67, 64, 62, 60, 67, 65, 64, 62, 60, 60]
LA_MENOR = [69, 71, 72, 74, 76, 72, 71, 68, 69, 76, 74, 72, 71, 69]

PRIMERA_NOTA_SEGUNDOS = 0.7


def melodia(duraciones, alturas, bpm, jitter=0.0, semilla=0) -> list[NotaMusical]:
    rng = np.random.default_rng(semilla)
    pulso = 60.0 / bpm
    inicios = np.concatenate([[0.0], np.cumsum(duraciones[:-1])]) * pulso + PRIMERA_NOTA_SEGUNDOS
    inicios = inicios + rng.normal(0, jitter, len(inicios))
    return [
        NotaMusical(nota=alturas[i % len(alturas)], inicio=float(max(0.0, ini)),
                    duracion=0.9 * dur * pulso, velocidad=90)
        for i, (ini, dur) in enumerate(zip(inicios, duraciones, strict=True))
    ]


def _onsets(notas):
    return [n.inicio for n in notas]


# --- Tempo ---------------------------------------------------------------

PATRONES_CLAROS = pytest.mark.parametrize(
    "patron", [NEGRAS_Y_CORCHEAS, CON_BLANCAS, CON_PUNTILLO],
    ids=["negras+corcheas", "con-blancas", "con-puntillo"],
)


@pytest.mark.parametrize("bpm", [66, 80, 96, 110, 128])
@PATRONES_CLAROS
@pytest.mark.parametrize("semilla", [0, 1, 2])
def test_bpm_dentro_del_5_por_ciento_con_desprolijidad_de_tarareo(config, bpm, patron, semilla):
    notas = melodia(patron, DO_MAYOR, bpm, jitter=0.02, semilla=semilla)

    estimado, _ = estimar_bpm(_onsets(notas), config)

    assert estimado == pytest.approx(bpm, rel=0.05)


def _es_el_tempo_o_su_doble_o_mitad(estimado: float, real: float) -> bool:
    return min(abs(estimado / real - r) for r in (0.5, 1.0, 2.0)) <= 0.05


@pytest.mark.parametrize("bpm", [66, 80, 96, 110, 128, 145])
def test_solo_corcheas_se_lee_al_tempo_o_al_doble_nunca_a_otro(config, bpm):
    """
    Ocho corcheas seguidas a 66 son, para el oído, lo mismo que negras a 132:
    las dos lecturas son válidas. Lo que no puede pasar es un tempo que no
    sea ninguna de las dos (por ejemplo ×1.5, que convierte la melodía en
    tresillos).
    """
    notas = melodia(SOLO_CORCHEAS, DO_MAYOR, bpm, jitter=0.02)

    estimado, _ = estimar_bpm(_onsets(notas), config)

    assert _es_el_tempo_o_su_doble_o_mitad(estimado, bpm)


@PATRONES_CLAROS
@pytest.mark.parametrize("semilla", [0, 1, 2])
def test_tarareo_rapido_puede_leerse_a_la_mitad(config, patron, semilla):
    """
    A 145 BPM, un tarareo de negras también se siente "a la mitad" (72.5 con
    corcheas), y con ±20 ms de desprolijidad la lectura lenta a veces encaja
    mejor (1 de 9 casos sintéticos). Las dos son válidas; librosa desempata
    con audio real. Documentado como límite conocido, no ajustado a mano.
    """
    notas = melodia(patron, DO_MAYOR, 145, jitter=0.02, semilla=semilla)

    estimado, _ = estimar_bpm(_onsets(notas), config)

    assert _es_el_tempo_o_su_doble_o_mitad(estimado, 145)


def test_librosa_desempata_entre_un_tempo_y_su_doble(config):
    notas = melodia(SOLO_CORCHEAS, DO_MAYOR, 66, jitter=0.02)

    sin_librosa, _ = estimar_bpm(_onsets(notas), config)
    con_librosa, _ = estimar_bpm(_onsets(notas), config, bpm_librosa=66.5)

    assert sin_librosa == pytest.approx(132, rel=0.05)  # lectura "rápida", válida
    assert con_librosa == pytest.approx(66, rel=0.05)  # la segunda opinión inclina la balanza


def test_confianza_alta_si_las_notas_caen_en_la_grilla(config):
    exacta = melodia(NEGRAS_Y_CORCHEAS, DO_MAYOR, 100)
    desprolija = melodia(NEGRAS_Y_CORCHEAS, DO_MAYOR, 100, jitter=0.05)

    _, confianza_exacta = estimar_bpm(_onsets(exacta), config)
    _, confianza_desprolija = estimar_bpm(_onsets(desprolija), config)

    assert confianza_exacta > 0.95
    assert confianza_desprolija < confianza_exacta


# --- Tonalidad ------------------------------------------------------------

def test_tonalidad_do_mayor(config):
    nombre, correlacion = estimar_tonalidad(melodia(NEGRAS_Y_CORCHEAS, DO_MAYOR, 100))
    assert nombre == "C major"
    assert correlacion > 0.7


def test_tonalidad_la_menor(config):
    nombre, _ = estimar_tonalidad(melodia(NEGRAS_Y_CORCHEAS, LA_MENOR, 100))
    assert nombre == "A minor"


def test_tonalidad_con_bemol_se_escribe_con_b(config):
    mi_bemol = [n + 3 for n in DO_MAYOR]
    nombre, _ = estimar_tonalidad(melodia(NEGRAS_Y_CORCHEAS, mi_bemol, 100))
    assert nombre == "Eb major"  # music21 la llama "E-"; en el JSON va "Eb"


def test_las_notas_largas_pesan_mas_que_las_de_paso(config):
    """Un Fa# corto de paso no convierte Do mayor en Sol mayor."""
    alturas = [60, 64, 66, 67, 64, 60, 67, 60]
    duraciones = [2, 1, 0.25, 1.75, 1, 2, 1, 4]
    nombre, _ = estimar_tonalidad(melodia(duraciones, alturas, 100))
    assert nombre == "C major"


# --- Pulso 0 y cuantización suave ----------------------------------------

def test_el_pulso_cero_cae_en_la_primera_nota_y_la_grilla_es_correcta(config):
    notas = melodia(NEGRAS_Y_CORCHEAS, DO_MAYOR, 100, jitter=0.01)

    resultado = analizar(notas, None, config)

    assert resultado.desfasePulsoSegundos == pytest.approx(PRIMERA_NOTA_SEGUNDOS, abs=0.03)
    assert resultado.melodiaCuantizada[0].inicioPulsos == 0.0
    esperados = np.concatenate([[0.0], np.cumsum(NEGRAS_Y_CORCHEAS[:-1])])
    assert [n.inicioPulsos for n in resultado.melodiaCuantizada] == pytest.approx(list(esperados))
    assert all(n.ajustada for n in resultado.melodiaCuantizada)


def test_una_nota_lejos_de_la_grilla_se_respeta_como_se_canto(config):
    """Cuantización suave: un corrimiento grande es intención, no error."""
    notas = melodia(NEGRAS_Y_CORCHEAS, DO_MAYOR, 100)
    semicorchea = 60.0 / 100 / 4
    corrida = notas[5].model_copy(update={"inicio": notas[5].inicio + 0.45 * semicorchea})
    notas[5] = corrida

    resultado = analizar(notas, None, config)
    nota = resultado.melodiaCuantizada[5]

    assert nota.ajustada is False
    assert nota.inicioPulsos % 0.25 != 0  # quedó entre dos semicorcheas, como se cantó


def test_ninguna_nota_queda_con_duracion_cero(config):
    notas = melodia(NEGRAS_Y_CORCHEAS, DO_MAYOR, 100, jitter=0.03)
    notas[3] = notas[3].model_copy(update={"duracion": 0.09})  # muy corta

    resultado = analizar(notas, None, config)

    assert all(n.duracionPulsos > 0 for n in resultado.melodiaCuantizada)


# --- Casos límite y salida ------------------------------------------------

def test_con_muy_pocas_notas_falla_con_mensaje_accionable(config):
    notas = melodia([1, 1, 2], DO_MAYOR, 100)

    with pytest.raises(ErrorAudioInvalido) as info:
        analizar(notas, None, config)

    assert info.value.motivo == MotivoFallo.SIN_MELODIA_CLARA
    assert "frase más larga" in info.value.mensaje


def test_el_midi_lleva_el_tempo_entendido_y_las_notas_en_la_grilla(tmp_path, config):
    notas = melodia(NEGRAS_Y_CORCHEAS, DO_MAYOR, 92)
    resultado = analizar(notas, None, config)
    ruta = tmp_path / "melodia.mid"

    escribir_midi(resultado.melodiaCuantizada, ruta, tempo=resultado.bpm)

    midi = pretty_midi.PrettyMIDI(str(ruta))
    assert midi.get_tempo_changes()[1][0] == pytest.approx(resultado.bpm, rel=0.001)
    pulso = 60.0 / resultado.bpm
    inicios_en_pulsos = [n.start / pulso for n in midi.instruments[0].notes]
    assert inicios_en_pulsos[0] == pytest.approx(0.0, abs=0.01)
    assert all(abs(x * 4 - round(x * 4)) < 0.02 for x in inicios_en_pulsos)  # en semicorcheas


# --- ¿Tiene pulso? Ritmo medido vs. ritmo libre ----------------------------

# Distancias reales entre notas de tests/audio/mi_tarareo.m4a (2026-11-14):
# tiempo libre, sin pulso estable (alineación al nivel del azar).
IOIS_TARAREO_REAL = [0.94, 0.57, 1.08, 0.58, 0.57, 1.29, 1.46, 0.15, 1.38, 0.69,
                     0.60, 1.46, 0.20, 1.30, 1.45, 1.47, 0.93]


def _notas_desde_iois(iois, alturas=DO_MAYOR) -> list[NotaMusical]:
    inicios = np.concatenate([[0.5], 0.5 + np.cumsum(iois)])
    duraciones = list(iois) + [0.8]
    return [
        NotaMusical(nota=alturas[i % len(alturas)], inicio=float(ini),
                    duracion=float(min(dur * 0.9, 1.5)), velocidad=80)
        for i, (ini, dur) in enumerate(zip(inicios, duraciones, strict=True))
    ]


def test_melodia_con_pulso_se_trata_como_ritmo_medido(config):
    resultado = analizar(melodia(NEGRAS_Y_CORCHEAS, DO_MAYOR, 100, jitter=0.02), None, config)

    assert resultado.ritmo == "medido"
    assert resultado.bpm == pytest.approx(100, rel=0.05)
    assert resultado.confianzaBpm > 0.5


def test_tarareo_real_en_tiempo_libre_se_regulariza(config):
    notas = _notas_desde_iois(IOIS_TARAREO_REAL)

    resultado = analizar(notas, None, config)

    assert resultado.ritmo == "libre"
    assert "tiempo libre" in resultado.motivoRitmo
    # Sigue siendo la misma melodía: mismas alturas, mismo orden.
    assert [n.nota for n in resultado.melodiaCuantizada] == [n.nota for n in notas]
    # El ajuste fiel evita forzar el rubato a una grilla artificial.
    inicios = [n.inicioPulsos for n in resultado.melodiaCuantizada]
    assert inicios == sorted(inicios)
    originales = [(n.inicio-notas[0].inicio) * resultado.bpm / 60 for n in notas]
    assert max(abs(a-b) for a, b in zip(inicios, originales, strict=True)) <= .101
    assert "ajuste suave" in resultado.motivoRitmo
    for actual, siguiente in zip(resultado.melodiaCuantizada, resultado.melodiaCuantizada[1:], strict=False):
        assert actual.inicioPulsos + actual.duracionPulsos <= siguiente.inicioPulsos


def test_notas_al_azar_no_tienen_pulso(config):
    rng = np.random.default_rng(7)
    iois = rng.uniform(0.2, 1.6, 15)

    assert analizar(_notas_desde_iois(iois), None, config).ritmo == "libre"


def test_regularizar_conserva_las_proporciones_y_acorta_las_pausas():
    """
    A 120 BPM (pulso = 0.5 s): notas de 0.5 s → 1 tiempo; de 1 s → 2 tiempos.
    Una pausa de 3 s entre frases no se vuelve 6 tiempos: es un silencio de 2.
    """
    iois = [0.5, 0.5, 1.0, 0.5, 3.0, 0.5, 1.0]
    notas = _notas_desde_iois(iois)
    notas = [n.model_copy(update={"duracion": 0.45}) for n in notas]

    resultado = regularizar(notas, 120)

    inicios = [n.inicioPulsos for n in resultado]
    # 1 + 1 + 2 + 1, después la nota de la pausa (1 tiempo) + 2 de silencio, 1, 2
    assert inicios == [0, 1, 2, 4, 5, 8, 9, 11]
    assert resultado[4].duracionPulsos == 1.0  # la nota antes de la pausa suena lo que se cantó


def test_tempo_por_densidad_hace_que_la_nota_tipica_dure_un_tiempo(config):
    onsets = np.cumsum([0.0, 0.6, 0.6, 0.6, 1.2, 0.6, 4.0, 0.6, 0.6])  # 4 s = pausa, no cuenta
    assert tempo_por_densidad(onsets, config) == 100.0
