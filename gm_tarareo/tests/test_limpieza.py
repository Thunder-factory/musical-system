from app.modelos import MotivoDescarte
from app.pipeline.limpieza import (
    _detectar_octava_duplicada,
    _filtrar_fuera_de_rango,
    _filtrar_senal_debil,
    _fusionar_notas_partidas,
    limpiar_notas,
)
from app.pipeline.melodia import NotaCruda

# Notas crudas reales devueltas por basic-pitch para tests/audio/mi_tarareo.wav
# (capturadas corriendo el pipeline una vez; ver CLAUDE.md). Congeladas acá
# para que este test sea rápido y determinista: no depende de correr
# basic-pitch/TensorFlow en cada corrida de pytest.
NOTAS_CRUDAS_REALES = [
    NotaCruda(49, 0.37, 1.20, 0.68), NotaCruda(50, 1.31, 1.45, 0.66),
    NotaCruda(46, 1.88, 2.09, 0.63), NotaCruda(58, 1.90, 2.58, 0.57),
    NotaCruda(46, 2.09, 2.96, 0.54), NotaCruda(47, 2.96, 3.14, 0.58),
    NotaCruda(46, 3.54, 3.68, 0.62), NotaCruda(58, 3.54, 3.91, 0.50),
    NotaCruda(46, 3.68, 4.11, 0.63), NotaCruda(47, 4.11, 4.96, 0.59),
    NotaCruda(59, 4.57, 4.73, 0.33), NotaCruda(46, 5.40, 5.56, 0.55),
    NotaCruda(46, 5.56, 5.87, 0.59), NotaCruda(86, 5.58, 5.76, 0.35),
    NotaCruda(47, 5.87, 6.28, 0.37), NotaCruda(51, 6.87, 7.00, 0.61),
    NotaCruda(50, 7.02, 7.40, 0.73), NotaCruda(50, 7.40, 7.72, 0.72),
    NotaCruda(47, 8.40, 8.93, 0.42), NotaCruda(47, 9.08, 9.30, 0.40),
    NotaCruda(46, 9.69, 10.65, 0.57), NotaCruda(58, 9.71, 9.85, 0.34),
    NotaCruda(58, 9.86, 10.68, 0.58), NotaCruda(45, 11.15, 11.30, 0.52),
    NotaCruda(46, 11.35, 11.93, 0.54), NotaCruda(58, 11.38, 11.94, 0.45),
    NotaCruda(48, 12.65, 12.99, 0.83), NotaCruda(60, 12.85, 13.16, 0.35),
    NotaCruda(48, 12.99, 13.36, 0.67), NotaCruda(51, 14.10, 14.42, 0.77),
    NotaCruda(51, 14.42, 14.77, 0.60), NotaCruda(51, 14.77, 14.90, 0.49),
    NotaCruda(46, 15.58, 16.14, 0.54), NotaCruda(44, 16.51, 16.65, 0.42),
]


def _hay_par_solapado_a_una_octava(notas) -> bool:
    for i, a in enumerate(notas):
        for b in notas[i + 1:]:
            solapan = a.inicio < (b.inicio + b.duracion) and b.inicio < (a.inicio + a.duracion)
            if solapan and abs(a.nota - b.nota) == 12:
                return True
    return False


def test_octava_duplicada_conserva_la_mas_cercana_a_la_mediana():
    # mediana de referencia 46 (el registro real de la voz) -> debe ganar 46
    # aunque el armónico (58) tenga más amplitud.
    notas = [NotaCruda(46, 1.90, 2.11, 0.40), NotaCruda(58, 1.88, 2.61, 0.60)]
    supervivientes, descartadas = _detectar_octava_duplicada(notas, semitonos_octava=12, mediana_referencia=46)

    assert [n.nota for n in supervivientes] == [46]
    assert descartadas == [(notas[1], MotivoDescarte.OCTAVA_DUPLICADA)]


def test_octava_duplicada_favorece_el_subarmonico_si_esta_mas_cerca_de_la_mediana():
    # el mismo caso pero con la mediana apuntando al registro de arriba:
    # ahora debe ganar el que está cerca de esa mediana, no el de mayor amplitud.
    notas = [NotaCruda(46, 1.90, 2.11, 0.60), NotaCruda(58, 1.88, 2.61, 0.40)]
    supervivientes, descartadas = _detectar_octava_duplicada(notas, semitonos_octava=12, mediana_referencia=58)

    assert [n.nota for n in supervivientes] == [58]
    assert descartadas == [(notas[0], MotivoDescarte.OCTAVA_DUPLICADA)]


def test_octava_duplicada_empata_en_distancia_desempata_por_amplitud():
    # mediana=52, ambas a 6 semitonos exactos -> empate, gana la de mayor amplitud
    notas = [NotaCruda(46, 1.90, 2.11, 0.70), NotaCruda(58, 1.88, 2.61, 0.30)]
    supervivientes, descartadas = _detectar_octava_duplicada(notas, semitonos_octava=12, mediana_referencia=52)

    assert [n.nota for n in supervivientes] == [46]
    assert descartadas == [(notas[1], MotivoDescarte.OCTAVA_DUPLICADA)]


def test_octava_duplicada_no_afecta_notas_que_no_se_solapan():
    notas = [NotaCruda(46, 0.0, 1.0, 0.5), NotaCruda(58, 5.0, 6.0, 0.5)]
    supervivientes, descartadas = _detectar_octava_duplicada(notas, semitonos_octava=12, mediana_referencia=46)

    assert len(supervivientes) == 2
    assert descartadas == []


def test_fusion_de_notas_partidas_con_hueco_chico():
    notas = [NotaCruda(46, 1.90, 2.11, 0.5), NotaCruda(46, 2.11, 3.00, 0.7)]
    fusionadas, descartadas = _fusionar_notas_partidas(notas, hueco_maximo_segundos=0.05)

    assert len(fusionadas) == 1
    assert fusionadas[0].inicio == 1.90
    assert fusionadas[0].fin == 3.00
    assert len(descartadas) == 1
    assert descartadas[0][1] == MotivoDescarte.FUSIONADA


def test_fusion_no_junta_notas_con_hueco_grande():
    notas = [NotaCruda(46, 0.0, 1.0, 0.5), NotaCruda(46, 5.0, 6.0, 0.5)]
    fusionadas, descartadas = _fusionar_notas_partidas(notas, hueco_maximo_segundos=0.05)

    assert len(fusionadas) == 2
    assert descartadas == []


def test_filtrar_fuera_de_rango_descarta_espuria():
    notas = [NotaCruda(60, 0, 1, 0.6), NotaCruda(62, 1, 2, 0.6), NotaCruda(86, 2, 3, 0.5)]
    supervivientes, descartadas = _filtrar_fuera_de_rango(notas, margen_semitonos=12)

    assert 86 not in [n.nota for n in supervivientes]
    assert descartadas[0][1] == MotivoDescarte.FUERA_DE_RANGO


def test_filtrar_senal_debil_descarta_por_amplitud_y_duracion():
    notas = [
        NotaCruda(60, 0.0, 1.0, 0.60),   # sobrevive
        NotaCruda(61, 1.0, 1.05, 0.60),  # muy corta (50ms)
        NotaCruda(62, 2.0, 2.50, 0.10),  # muy débil (amp 0.10)
    ]
    supervivientes, descartadas = _filtrar_senal_debil(notas, amplitud_minima=0.40, duracion_minima_segundos=0.08)

    assert [n.nota for n in supervivientes] == [60]
    assert {d[1] for d in descartadas} == {MotivoDescarte.SENAL_DEBIL}


def test_limpiar_notas_reales_da_entre_12_y_18_finales(config):
    notas_finales, notas_descartadas = limpiar_notas(NOTAS_CRUDAS_REALES, config)

    assert 12 <= len(notas_finales) <= 18
    assert len(notas_finales) + len(notas_descartadas) == len(NOTAS_CRUDAS_REALES)


def test_limpiar_notas_reales_no_deja_octavas_duplicadas(config):
    notas_finales, _ = limpiar_notas(NOTAS_CRUDAS_REALES, config)
    assert not _hay_par_solapado_a_una_octava(notas_finales)


def test_limpiar_notas_reales_conserva_el_fundamental_no_el_armonico(config):
    # regresión: a ~1.9s hay un fundamental (46, la voz real está en 45-51)
    # fragmentado en dos partes de amplitud desigual, con su armónico (58)
    # superpuesto. Con amplitud como desempate el armónico ganaba (una vez
    # promediada la fusión, el fundamental quedaba más débil que el 58) y
    # la melodía se transcribía una octava arriba en ese tramo.
    notas_finales, _ = limpiar_notas(NOTAS_CRUDAS_REALES, config)

    nota_en_1_9s = next(n for n in notas_finales if n.inicio <= 1.9 < n.inicio + n.duracion)
    assert nota_en_1_9s.nota == 46
    assert 58 not in [n.nota for n in notas_finales if 1.8 <= n.inicio <= 2.6]


def test_limpiar_notas_reales_produce_notas_musicales_validas(config):
    notas_finales, _ = limpiar_notas(NOTAS_CRUDAS_REALES, config)

    for nota in notas_finales:
        assert 0 <= nota.nota <= 127
        assert 0 <= nota.velocidad <= 127
        assert nota.duracion > 0


def test_fusion_no_acorta_una_nota_que_contiene_a_otra():
    # Regresión: una nota contenida dentro de otra del mismo pitch hacía que
    # la fusión terminara en el fin de la nota de adentro (1.0->2.0).
    contenedora = NotaCruda(60, 1.0, 3.0, 0.8)
    contenida = NotaCruda(60, 1.5, 2.0, 0.8)
    resultado, descartadas = _fusionar_notas_partidas([contenedora, contenida], 0.05)

    assert [(n.inicio, n.fin) for n in resultado] == [(1.0, 3.0)]
    assert descartadas == [(contenida, MotivoDescarte.FUSIONADA)]
