"""
Tarareos sintéticos con notas conocidas (la "respuesta correcta" para medir).

Los tarareos reales de tests/audio no tienen las notas anotadas, así que no
sirven para calcular precisión. Acá se generan melodías al azar dentro de una
escala y se sintetizan imitando lo que hace difícil a un tarareo real:

- desafinación por nota (la gente no canta exacto: ±25 cents de desvío típico),
- vibrato que aparece después del ataque,
- glissando (portamento) al pasar de una nota a otra sin respirar,
- timbre de "mmm" (pocos armónicos), respiración y ruido de fondo,
- registro grave (voz masculina) o agudo (femenina).

Todo es determinista a partir de la semilla, para que las comparaciones se
puedan repetir.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SR = 22050
ESCALAS = {'mayor': (0, 2, 4, 5, 7, 9, 11), 'menor': (0, 2, 3, 5, 7, 8, 10)}


@dataclass(frozen=True)
class NotaReferencia:
    nota: int
    inicio: float
    fin: float


@dataclass(frozen=True)
class Tarareo:
    nombre: str
    audio: np.ndarray
    notas: list[NotaReferencia]
    registro: str
    snr_db: float


def _melodia(rng: np.random.Generator, registro: str) -> list[NotaReferencia]:
    tonica = int(rng.integers(0, 12))
    escala = ESCALAS[rng.choice(list(ESCALAS))]
    base = (48 if registro == 'grave' else 60) + tonica
    pulso = 60 / float(rng.uniform(70, 130))
    grado, t, notas = int(rng.integers(0, 5)), 0.25, []
    for _ in range(int(rng.integers(9, 17))):
        grado = int(np.clip(grado + rng.choice([-3, -2, -1, -1, 0, 1, 1, 2, 3]), -3, 10))
        octava, indice = divmod(grado, 7)
        nota = base + 12 * octava + escala[indice]
        duracion = pulso * float(rng.choice([0.5, 0.75, 1, 1, 1.5, 2]))
        notas.append(NotaReferencia(nota, round(t, 4), round(t + duracion, 4)))
        t += duracion
        if rng.random() < 0.15:  # respiración entre frases
            t += float(rng.uniform(0.15, 0.4))
    return notas


def _sintetizar(rng: np.random.Generator, notas: list[NotaReferencia], snr_db: float) -> np.ndarray:
    total = int((notas[-1].fin + 0.4) * SR)
    f0 = np.zeros(total)
    amplitud = np.zeros(total)
    anterior_hz, anterior_fin = None, -1.0
    for nota in notas:
        i0, i1 = int(nota.inicio * SR), int(nota.fin * SR)
        n = i1 - i0
        t = np.arange(n) / SR
        objetivo = 440 * 2 ** ((nota.nota - 69 + rng.normal(0, 0.25)) / 12)
        cents = np.zeros(n)
        inicio_vibrato = min(0.18, (nota.fin - nota.inicio) * 0.4)
        profundidad = rng.uniform(15, 40)
        cents += np.where(t > inicio_vibrato, profundidad * np.sin(2 * np.pi * rng.uniform(4.5, 6.5) * t), 0)
        cents += np.cumsum(rng.normal(0, 0.4, n)) * 0.05  # deriva lenta
        trayectoria = objetivo * 2 ** (cents / 1200)
        if anterior_hz and abs(nota.inicio - anterior_fin) < 1e-3:  # legato: glissando
            g = min(n, int(rng.uniform(0.03, 0.08) * SR))
            trayectoria[:g] = np.geomspace(anterior_hz, trayectoria[g - 1] if g else objetivo, g)
        f0[i0:i1] = trayectoria
        envolvente = np.ones(n)
        ataque, caida = min(n, int(0.03 * SR)), min(n, int(0.05 * SR))
        envolvente[:ataque] = np.linspace(0, 1, ataque)
        envolvente[n - caida:] *= np.linspace(1, 0.3, caida)
        amplitud[i0:i1] = envolvente * rng.uniform(0.6, 1.0)
        anterior_hz, anterior_fin = objetivo, nota.fin

    fase = 2 * np.pi * np.cumsum(f0) / SR
    voz = sum(np.sin(k * fase) / k ** 2.2 for k in range(1, 12))  # "mmm": pocos armónicos
    voz *= amplitud
    respiracion = rng.normal(0, 1, total) * amplitud * 0.02
    senal = voz + respiracion
    potencia = np.mean(senal[amplitud > 0] ** 2)
    ruido = rng.normal(0, np.sqrt(potencia / 10 ** (snr_db / 10)), total)
    audio = senal + ruido
    return (0.8 * audio / np.max(np.abs(audio))).astype(np.float32)


def generar(cantidad: int = 40, semilla: int = 2026) -> list[Tarareo]:
    rng = np.random.default_rng(semilla)
    tarareos = []
    for i in range(cantidad):
        registro = 'grave' if i % 2 == 0 else 'agudo'
        snr = float(rng.uniform(12, 30))
        notas = _melodia(rng, registro)
        tarareos.append(Tarareo(f'sint-{i:02d}', _sintetizar(rng, notas, snr), notas, registro, snr))
    return tarareos
