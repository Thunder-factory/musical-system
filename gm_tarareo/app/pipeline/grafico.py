"""Datos del gráfico "tu tarareo vs. la canción" (sin dibujar nada aquí)."""

from __future__ import annotations

import numpy as np

from app.modelos import AnalisisMusical, GraficoTarareo, NotaMusical

PASO_SEGUNDOS = 0.05


def contorno(tiempos, alturas, validas, paso: float = PASO_SEGUNDOS) -> list[float | None]:
    """Mediana de la altura válida en cada tramo de `paso` s; `None` donde no hay voz."""
    if len(tiempos) == 0:
        return []
    tramos = np.floor(np.asarray(tiempos) / paso).astype(int)
    total = int(tramos[-1]) + 1
    resultado: list[float | None] = [None] * total
    alturas, validas = np.asarray(alturas), np.asarray(validas, dtype=bool)
    for tramo in range(total):
        valores = alturas[(tramos == tramo) & validas]
        if len(valores):
            resultado[tramo] = round(float(np.median(valores)), 2)
    while resultado and resultado[-1] is None:
        resultado.pop()
    return resultado


def datos_grafico(curva: list[float | None], notas: list[NotaMusical],
                  analisis: AnalisisMusical) -> GraficoTarareo:
    """Curva medida + notas detectadas + melodía cuantizada, todo en segundos del tarareo."""
    segundos_por_pulso = 60 / analisis.bpm
    cancion = [
        [n.nota, round(analisis.desfasePulsoSegundos + n.inicioPulsos * segundos_por_pulso, 3),
         round(n.duracionPulsos * segundos_por_pulso, 3)]
        for n in analisis.melodiaCuantizada
    ]
    return GraficoTarareo(
        pasoSegundos=PASO_SEGUNDOS,
        contorno=curva,
        notas=[[n.nota, round(n.inicio, 3), round(n.duracion, 3)] for n in notas],
        cancion=cancion,
    )
