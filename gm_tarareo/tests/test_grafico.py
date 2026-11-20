"""Datos del gráfico tarareo vs. canción."""

import numpy as np

from app.modelos import AnalisisMusical, NotaCuantizada, NotaMusical
from app.pipeline.grafico import PASO_SEGUNDOS, contorno, datos_grafico


def test_contorno_mediana_por_tramo_y_huecos_sin_voz():
    tiempos = np.arange(0, 0.3, 0.01)  # 30 ventanas = 6 tramos de 50 ms
    alturas = np.full(len(tiempos), 60.0)
    alturas[10:20] = 62.04
    validas = np.ones(len(tiempos), dtype=bool)
    validas[20:] = False  # el final no tiene voz: no se exporta

    curva = contorno(tiempos, alturas, validas)

    assert curva == [60.0, 60.0, 62.04, 62.04]


def test_contorno_marca_silencios_intermedios_con_none():
    tiempos = np.arange(0, 0.2, 0.01)
    validas = np.ones(len(tiempos), dtype=bool)
    validas[5:10] = False
    curva = contorno(tiempos, np.full(len(tiempos), 57.0), validas)
    assert curva == [57.0, None, 57.0, 57.0]


def test_melodia_de_la_cancion_en_segundos_del_tarareo():
    analisis = AnalisisMusical(
        bpm=120, confianzaBpm=0.8, ritmo="medido", motivoRitmo="", desfasePulsoSegundos=0.25,
        tonalidad="C major", confianzaTonalidad=0.9,
        melodiaCuantizada=[NotaCuantizada(nota=60, inicioPulsos=2, duracionPulsos=1, velocidad=90, ajustada=False)],
    )
    notas = [NotaMusical(nota=61, inicio=1.2, duracion=0.4, velocidad=80)]

    grafico = datos_grafico([60.0, None], notas, analisis)

    assert grafico.pasoSegundos == PASO_SEGUNDOS
    assert grafico.contorno == [60.0, None]
    assert grafico.notas == [[61, 1.2, 0.4]]
    assert grafico.cancion == [[60, 1.25, 0.5]]  # 0.25 + 2 pulsos × 0.5 s
