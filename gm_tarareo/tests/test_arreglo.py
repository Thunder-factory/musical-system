"""
Tests de la etapa 7 (arreglo).

La entrada se arma con las etapas reales (análisis, armonía, estilo) sobre
melodías sintéticas, así se prueba el arreglo con datos como los del pipeline.
"""

from itertools import pairwise

import numpy as np
import pretty_midi
import pytest

from app.modelos import NotaMusical
from app.pipeline.analisis import analizar
from app.pipeline.armonia import armonizar
from app.pipeline.arreglo import (
    ESTILOS,
    PULSOS_POR_COMPAS,
    Acorde,
    Evento,
    _septima_no_choca,
    arreglar,
    elegir_variante,
    planificar_estructura,
    transponer_diatonico,
)
from app.pipeline.estilo import inferir_estilo
from app.pipeline.salida import escribir_arreglo_midi

# Do mayor, 4 compases a 100 BPM: Do-Mi-Sol | Fa-La-Do | Sol-Si-Re | Do
FRASE = [(60, 1), (64, 1), (67, 2), (65, 1), (69, 1), (72, 2), (67, 1), (71, 1), (74, 2), (72, 4)]


def _notas(frase, bpm=100.0, inicio=0.5) -> list[NotaMusical]:
    pulso, t, notas = 60.0 / bpm, inicio, []
    for nota, dur in frase:
        notas.append(NotaMusical(nota=nota, inicio=t, duracion=dur * pulso * 0.92, velocidad=90))
        t += dur * pulso
    return notas


def _entrada(config, preset: str, frase=FRASE):
    notas = _notas(frase)
    analisis = analizar(notas, None, config)
    armonia = armonizar(analisis.melodiaCuantizada, analisis.tonalidad)
    estilo = inferir_estilo(notas, analisis).model_copy(update={"preset": preset})
    return analisis, armonia, estilo


def _variantes():
    return [(preset, v.nombre) for preset, e in ESTILOS.items() for v in e.variantes]


# --- Todos los estilos y variantes -----------------------------------------

@pytest.mark.parametrize("preset, variante", _variantes())
def test_cada_estilo_y_variante_genera_una_cancion_valida(config, tmp_path, preset, variante):
    analisis, armonia, estilo = _entrada(config, preset)

    resultado = arreglar(analisis, armonia, estilo, variante=variante)
    ruta = tmp_path / "arreglo.mid"
    escribir_arreglo_midi(resultado, ruta)

    arreglo = resultado.arreglo
    assert arreglo.variante == variante
    assert 60 <= arreglo.duracionSegundos <= 90
    midi = pretty_midi.PrettyMIDI(str(ruta))
    assert midi.get_end_time() == pytest.approx(arreglo.duracionSegundos, abs=2.5)
    roles = {p.rol for p in arreglo.pistas}
    assert {"melodia", "acompanamiento", "bajo"} <= roles
    for instrumento, pista in zip(midi.instruments, arreglo.pistas, strict=True):
        assert instrumento.is_drum == pista.bateria
        assert instrumento.notes, f"la pista {pista.nombre} quedó vacía"


def test_dos_estilos_distintos_suenan_distinto(config):
    pop = arreglar(*_entrada(config, "pop"))
    epico = arreglar(*_entrada(config, "epico"))
    assert {p.programa for p in pop.arreglo.pistas} != {p.programa for p in epico.arreglo.pistas}


# --- Estructura ------------------------------------------------------------

def test_estructura_contigua_desde_el_compas_cero_con_intro_y_outro(config):
    arreglo = arreglar(*_entrada(config, "pop")).arreglo

    secciones = arreglo.estructura
    assert secciones[0].nombre == "intro" and secciones[-1].nombre == "outro"
    assert secciones[0].compasInicio == 0
    for actual, siguiente in pairwise(secciones):
        assert actual.compasInicio + actual.compases == siguiente.compasInicio
    assert sum(s.compases for s in secciones) == arreglo.compases


def test_tarareo_largo_y_rapido_usa_menos_repeticiones():
    corto = planificar_estructura(compases_a=4, bpm=100)
    largo = planificar_estructura(compases_a=14, bpm=126)

    assert len(largo) < len(corto)
    assert "A'" not in [n for n, _ in largo]


def test_tarareo_corto_agrega_secciones_hasta_llegar_a_60_segundos():
    secciones = planificar_estructura(compases_a=2, bpm=120)
    segundos = sum(c for _, c in secciones) * PULSOS_POR_COMPAS * 60 / 120
    assert 60 <= segundos <= 90


# --- Contenido musical -----------------------------------------------------

def test_la_melodia_del_tarareo_suena_en_cada_seccion_a(config):
    analisis, armonia, estilo = _entrada(config, "balada")
    resultado = arreglar(analisis, armonia, estilo)

    alturas_tarareo = [n.nota for n in analisis.melodiaCuantizada]
    melodia = [e for e in resultado.eventos if e.pista == "melodia"]
    for seccion in resultado.arreglo.estructura:
        if seccion.nombre not in ("A", "A'", "A final"):
            continue
        inicio = seccion.compasInicio * PULSOS_POR_COMPAS
        fin = inicio + seccion.compases * PULSOS_POR_COMPAS
        en_seccion = [e.nota for e in melodia if inicio <= e.inicio < fin]
        desplazamiento = en_seccion[0] - alturas_tarareo[0]
        assert desplazamiento % 12 == 0  # misma melodía, a lo sumo en otra octava
        assert [n - desplazamiento for n in en_seccion] == alturas_tarareo


def test_el_bajo_toca_la_fundamental_del_acorde(config):
    analisis, armonia, estilo = _entrada(config, "pop")
    resultado = arreglar(analisis, armonia, estilo)

    primera_a = next(s for s in resultado.arreglo.estructura if s.nombre == "A")
    inicio = primera_a.compasInicio * PULSOS_POR_COMPAS
    raices = {round(a.inicioPulsos) + inicio: a.notas[0] % 12 for a in armonia.progresion}
    for e in resultado.eventos:
        if e.pista == "bajo" and e.inicio in raices:
            assert e.nota % 12 == raices[e.inicio]


def test_la_melodia_nunca_se_superpone_consigo_misma(config):
    resultado = arreglar(*_entrada(config, "rock_suave"))
    melodia = sorted((e for e in resultado.eventos if e.pista == "melodia"), key=lambda e: e.inicio)
    for actual, siguiente in pairwise(melodia):
        assert actual.inicio + actual.duracion <= siguiente.inicio + 1e-6


def test_el_mismo_tarareo_da_exactamente_la_misma_cancion(config):
    entrada = _entrada(config, "lofi")
    assert arreglar(*entrada).eventos == arreglar(*entrada).eventos


def test_la_nota_de_entrada_suena_antes_del_primer_tiempo(config):
    """Con anacrusa, la nota de entrada de A cae al final de la intro."""
    frase_con_entrada = [(67, 1)] + FRASE
    analisis, armonia, estilo = _entrada(config, "pop", frase_con_entrada)
    assert armonia.anacrusaPulsos > 0

    resultado = arreglar(analisis, armonia, estilo)
    primera_a = next(s for s in resultado.arreglo.estructura if s.nombre == "A")
    inicio_a = primera_a.compasInicio * PULSOS_POR_COMPAS
    entrada = [e for e in resultado.eventos if e.pista == "melodia" and inicio_a - 4 <= e.inicio < inicio_a]
    assert [e.nota % 12 for e in entrada] == [67 % 12]


# --- Piezas sueltas --------------------------------------------------------

def test_la_septima_no_se_agrega_si_la_melodia_canta_a_un_semitono():
    do_mayor = Acorde(0.0, 4.0, fundamental=0, calidad="mayor", grado="I")  # maj7 = Si
    canta_do = [Evento("melodia", 72, 0.0, 2.0, 90)]  # Do está a un semitono de Si
    canta_mi = [Evento("melodia", 64, 0.0, 2.0, 90)]

    assert not _septima_no_choca(do_mayor, canta_do)
    assert _septima_no_choca(do_mayor, canta_mi)


@pytest.mark.parametrize("nota, grados, esperado", [(64, 1, 65), (71, 1, 72), (60, 4, 67), (67, -2, 64)])
def test_transposicion_diatonica_en_do_mayor(nota, grados, esperado):
    assert transponer_diatonico(nota, grados, tonica=0, modo="mayor") == esperado


def test_la_variante_sale_de_los_rasgos_cuando_deciden(config):
    _, _, estilo = _entrada(config, "balada")
    ligado = estilo.rasgos.model_copy(update={"articulacion": 0.95})
    assert elegir_variante("balada", ligado, huella=0).nombre == "cuerdas"
    assert elegir_variante("balada", ligado, huella=12345).nombre == "cuerdas"


def test_sin_rasgos_decisivos_la_variante_sale_de_la_huella_y_es_estable(config):
    _, _, estilo = _entrada(config, "pop")
    elegidas = {elegir_variante("pop", estilo.rasgos, huella=h).nombre for h in range(30)}
    assert len(elegidas) == 3  # hay variedad entre tarareos distintos
    assert elegir_variante("pop", estilo.rasgos, 7) == elegir_variante("pop", estilo.rasgos, 7)


def test_volumen_dentro_de_rango_midi(config):
    resultado = arreglar(*_entrada(config, "epico"))
    velocidades = np.array([e.velocidad for e in resultado.eventos])
    assert velocidades.min() >= 1 and velocidades.max() <= 127


# --- Mejoras del 2026-11-14 ------------------------------------------------

def _seccion(resultado, nombre):
    s = next(x for x in resultado.arreglo.estructura if x.nombre == nombre)
    inicio = s.compasInicio * PULSOS_POR_COMPAS
    return inicio, inicio + s.compases * PULSOS_POR_COMPAS


def _acordes_de(eventos, pista="acompanamiento"):
    """Agrupa las notas de una pista que empiezan juntas: {inicio: [notas]}."""
    grupos = {}
    for e in eventos:
        if e.pista == pista:
            grupos.setdefault(e.inicio, []).append(e.nota)
    return {t: sorted(v) for t, v in sorted(grupos.items())}


def test_enlace_de_voces_mueve_poco_el_acompanamiento(config):
    """Con enlace de voces, cada voz se mueve en promedio menos de 3 semitonos entre acordes."""
    resultado = arreglar(*_entrada(config, "pop"), variante="piano")
    grupos = [v for v in _acordes_de(resultado.eventos).values() if len(v) >= 3]
    saltos = [sum(min(abs(n - m) for m in anterior) for n in actual) / len(actual)
              for anterior, actual in pairwise(grupos) if anterior != actual]
    assert saltos and float(np.mean(saltos)) < 3.0


def test_redoble_al_final_de_cada_seccion_con_bateria_y_platillo_al_entrar(config):
    resultado = arreglar(*_entrada(config, "pop"))
    bateria = [e for e in resultado.eventos if e.pista == "bateria"]
    inicio_a2, _ = _seccion(resultado, "A'")

    # Redoble: cajas en semicorcheas en el último compás de A (los tiempos 3-4 antes de A').
    redoble = [e for e in bateria if e.nota == 38 and inicio_a2 - 2 <= e.inicio < inicio_a2]
    assert len(redoble) >= 5
    # Platillo en el primer tiempo de A'.
    assert any(e.nota == 49 and e.inicio == pytest.approx(inicio_a2) for e in bateria)


def test_el_bajo_se_acerca_al_acorde_siguiente_con_una_nota_de_paso(config):
    analisis, armonia, estilo = _entrada(config, "pop")
    resultado = arreglar(analisis, armonia, estilo)
    bajo = sorted((e for e in resultado.eventos if e.pista == "bajo"), key=lambda e: e.inicio)

    pasos = 0
    for anterior, siguiente in pairwise(bajo):
        distancia = abs(siguiente.nota - anterior.nota)
        if siguiente.inicio - anterior.inicio == pytest.approx(0.5) and distancia == 1:
            pasos += 1
    assert pasos >= 3  # una aproximación cromática antes de varios cambios de acorde


def test_la_seccion_b_varia_entre_tarareos(config):
    from app.pipeline.arreglo import elegir_progresion_b

    elegidas = {elegir_progresion_b("mayor", h) for h in range(0, 300, 7)}
    assert len(elegidas) == 3
    assert all(p[-1] == "V" for p in elegidas)  # todas vuelven a A por la dominante


def test_a_prima_usa_un_acompanamiento_mas_lleno_que_a(config):
    resultado = arreglar(*_entrada(config, "pop"), variante="piano")
    a_inicio, a_fin = _seccion(resultado, "A")
    a2_inicio, a2_fin = _seccion(resultado, "A'")
    golpes = _acordes_de(resultado.eventos)

    en_a = [t for t in golpes if a_inicio <= t < a_fin]
    en_a2 = [t for t in golpes if a2_inicio <= t < a2_fin]
    assert len(en_a2) > len(en_a)


def test_segunda_voz_dobla_en_a_prima_y_hace_terceras_en_a_final(config):
    analisis, armonia, estilo = _entrada(config, "balada")
    resultado = arreglar(analisis, armonia, estilo)
    melodia = {e.inicio: e.nota for e in resultado.eventos if e.pista == "melodia"}
    segunda = {e.inicio: e.nota for e in resultado.eventos if e.pista == "segunda"}

    a2_inicio, a2_fin = _seccion(resultado, "A'")
    octavas = [abs(segunda[t] - melodia[t]) for t in segunda if a2_inicio <= t < a2_fin and t in melodia]
    assert octavas and all(d == 12 for d in octavas)

    af_inicio, af_fin = _seccion(resultado, "A final")
    terceras = [melodia[t] - segunda[t] for t in segunda if af_inicio <= t < af_fin and t in melodia]
    assert terceras and all(d in (3, 4) for d in terceras)  # tercera menor o mayor, por debajo


def test_la_intro_anticipa_el_primer_motivo(config):
    analisis, armonia, estilo = _entrada(config, "folk")
    resultado = arreglar(analisis, armonia, estilo)
    intro_inicio, intro_fin = _seccion(resultado, "intro")

    gancho = [e.nota % 12 for e in sorted(resultado.eventos, key=lambda e: e.inicio)
              if e.pista == "segunda" and intro_inicio <= e.inicio < intro_fin]
    assert gancho[:3] == [60 % 12, 64 % 12, 67 % 12]  # Do-Mi-Sol, el comienzo del tarareo


def test_crescendo_antes_de_a_final(config):
    resultado = arreglar(*_entrada(config, "rock_suave"))
    inicio_final, _ = _seccion(resultado, "A final")
    bajo = [e for e in resultado.eventos if e.pista == "bajo" and inicio_final - 8 <= e.inicio < inicio_final]

    primera_mitad = np.mean([e.velocidad for e in bajo if e.inicio < inicio_final - 4])
    segunda_mitad = np.mean([e.velocidad for e in bajo if e.inicio >= inicio_final - 4])
    assert segunda_mitad > primera_mitad


def test_el_outro_frena_y_sostiene_el_acorde_final(config):
    resultado = arreglar(*_entrada(config, "balada"))
    inicio_outro, _ = _seccion(resultado, "outro")
    acompanamiento = _acordes_de([e for e in resultado.eventos if e.inicio >= inicio_outro])
    inicios = list(acompanamiento)

    # Sin ritardando los dos acordes del outro estarían a 4 pulsos; frenando, a más.
    assert inicios[1] - inicios[0] > 4.0
    final = [e for e in resultado.eventos if e.pista == "acompanamiento" and e.inicio == inicios[-1]]
    assert all(e.duracion > PULSOS_POR_COMPAS for e in final)  # fermata
