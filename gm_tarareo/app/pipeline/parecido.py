"""
¿Cuánto de la melodía del tarareo suena en una versión producida con IA?

ACE-Step (modo cover) rehace la canción entera: no hay una pista de melodía
que comparar. Se transcribe el audio con IA con basic-pitch (polifónico) y,
por cada tramo de 50 ms donde la pista "Melodía" de `arreglo-N.mid` tiene una
nota, se mira si esa clase de altura (Do, Re…, en cualquier octava) suena en
el audio con IA (±100 ms). Al acierto se le descuenta el azar: la fracción de
clases que suenan en esos mismos tramos (un audio muy denso acierta "de
casualidad").

    puntaje = (acierto − azar) / (1 − azar)   ∈ [0, 1]

Calibración (docs/tarareo.md, 2026-11-19): la canción FluidSynth contra sí
misma da 0.97; covers del mismo tarareo 0.40-0.47 (fidelidad media/alta) y
0.21-0.33 (libre); otras melodías en la misma tonalidad y tempo, ≤ 0.10.
Por qué no croma del audio completo: mide tonalidad y armonía, no melodía
(covers de OTRO tarareo puntuaban igual que los del propio).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

PASO = 0.05
TOLERANCIA_TRAMOS = 2
PISTA_MELODIA = "Melodía"

# Umbrales del nivel que ve el usuario (ver calibración arriba).
UMBRAL_ALTO = 0.38
UMBRAL_MEDIO = 0.18


def notas_melodia(ruta_midi: Path) -> list[tuple[int, float, float]]:
    """(altura, inicio, fin) de la pista de melodía del arreglo, en segundos de la canción."""
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(ruta_midi))
    pista = next((i for i in midi.instruments if i.name == PISTA_MELODIA and not i.is_drum), None)
    if pista is None:
        raise ValueError(f"El MIDI no tiene la pista '{PISTA_MELODIA}'")
    return [(n.pitch, n.start, n.end) for n in pista.notes]


def clases_sonando(eventos, duracion: float) -> np.ndarray:
    """Matriz 12 × tramos: qué clases de altura suenan en cada tramo de PASO s."""
    tramos = int(duracion / PASO) + 1
    activas = np.zeros((12, tramos), dtype=bool)
    for inicio, fin, nota, *_ in eventos:
        a, b = int(inicio / PASO), min(tramos, int(fin / PASO) + 1)
        if a < tramos:
            activas[int(nota) % 12, a:b] = True
    return activas


def puntaje(melodia: list[tuple[int, float, float]], activas: np.ndarray) -> float:
    acierto = azar = total = 0.0
    for nota, inicio, fin in melodia:
        for tramo in range(int(inicio / PASO), int(fin / PASO)):
            if tramo >= activas.shape[1]:
                break
            ventana = activas[:, max(0, tramo - TOLERANCIA_TRAMOS): tramo + TOLERANCIA_TRAMOS + 1]
            acierto += bool(ventana[nota % 12].any())
            azar += float(ventana.any(axis=1).mean())
            total += 1
    if total == 0:
        return 0.0
    acierto, azar = acierto / total, azar / total
    if azar >= 1:
        return 0.0
    return float(np.clip((acierto - azar) / (1 - azar), 0, 1))


def nivel(valor: float) -> str:
    return "alto" if valor >= UMBRAL_ALTO else "medio" if valor >= UMBRAL_MEDIO else "bajo"


def medir_parecido(ruta_audio: Path, ruta_arreglo: Path) -> float:
    """Puntaje 0-1 de la melodía del arreglo dentro del audio (ver docstring del módulo)."""
    from basic_pitch.inference import predict

    from app.pipeline.melodia import cargar_modelo

    melodia = notas_melodia(ruta_arreglo)
    if not melodia:
        return 0.0
    _, _, eventos = predict(str(ruta_audio), cargar_modelo())
    duracion = max(fin for _, _, fin in melodia) + 1
    return round(puntaje(melodia, clases_sonando(eventos, duracion)), 3)
