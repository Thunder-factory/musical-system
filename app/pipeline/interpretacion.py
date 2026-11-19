"""Segunda opinión monofónica con evidencia acústica, sin catálogo de melodías."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import soundfile as sf

from app.modelos import AjusteAltura, InterpretacionTarareo

VENTANA = 2048
SALTO = 220


def medir_alturas(ruta: Path):
    """YIN + periodicidad: el estimador solo no distingue silencio o ruido."""
    import librosa

    audio, sr = sf.read(ruta, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    f0 = librosa.yin(audio, sr=sr, fmin=float(librosa.midi_to_hz(24)),
                     fmax=min(float(librosa.midi_to_hz(108)), sr / 3),
                     frame_length=VENTANA, hop_length=SALTO)
    ventanas = librosa.util.frame(np.pad(audio, (VENTANA // 2, VENTANA // 2)),
                                  frame_length=VENTANA, hop_length=SALTO).T
    rms = np.sqrt(np.mean(ventanas ** 2, axis=1))
    espectro = np.abs(np.fft.rfft((ventanas - ventanas.mean(axis=1, keepdims=True)) * np.hanning(VENTANA), axis=1))
    periodicidad = np.zeros(len(f0))
    fundamental = np.zeros(len(f0), dtype=bool)
    for i, frecuencia in enumerate(f0):
        lag = max(1, min(VENTANA // 2, round(sr / frecuencia)))
        a, b = ventanas[i, :-lag], ventanas[i, lag:]
        denominador = np.sqrt(np.dot(a, a) * np.dot(b, b))
        periodicidad[i] = np.dot(a, b) / denominador if denominador > 1e-10 else 0
        indice = max(1, round(frecuencia * VENTANA / sr))
        pico = np.max(espectro[i, max(1, indice-1):indice+2])
        # Una señal también es periódica al doble de su período. Exigir
        # energía en la fundamental propuesta evita validar esa falsa octava.
        fundamental[i] = pico >= .12 * np.max(espectro[i, 1:])
    activa = rms > max(1e-4, float(np.percentile(rms, 95)) * .05)
    validas = activa & (periodicidad >= .85) & fundamental
    return np.arange(len(f0)) * SALTO / sr, librosa.hz_to_midi(f0), validas, VENTANA / sr


def verificar_alturas(ruta: Path, crudas):
    """Corrige solo desacuerdos cercanos y estables; no fuerza notas a mayor/menor."""
    tiempos, alturas, validas, ventana = medir_alturas(ruta)
    medidas = []
    for nota in crudas:
        margen = min(ventana / 2, (nota.fin - nota.inicio) * .2)
        seleccion = (tiempos >= nota.inicio + margen) & (tiempos <= nota.fin - margen)
        valores = alturas[seleccion & validas]
        if len(valores) < 3 or len(valores) < .6 * np.count_nonzero(seleccion):
            medidas.append(None)
            continue
        mediana = float(np.median(valores))
        dispersion = float(np.median(np.abs(valores - mediana)))
        medidas.append(mediana if dispersion <= .28 else None)

    # Referencia de afinación del propio audio, no de la grabación de prueba.
    cercanas = [m for m, n in zip(medidas, crudas, strict=True)
                if m is not None and abs(m - n.nota) <= 1.2]
    referencia = 0.0
    if len(cercanas) >= 4:
        vector = np.mean(np.exp(2j * np.pi * np.array(cercanas)))
        propuesta = float(np.angle(vector) / (2 * np.pi))
        if abs(vector) >= .8 and abs(propuesta) <= .45:
            referencia = propuesta
    resultado, confirmadas, ajustes = [], set(), []
    for nota, medida in zip(crudas, medidas, strict=True):
        nueva = nota
        if medida is not None:
            destino = round(medida - referencia)
            estable = abs(medida - referencia - destino) <= .32
            # Las octavas siguen en limpieza: una segunda opinión de pitch
            # sola no basta para transponer una nota doce semitonos.
            if estable and abs(destino-nota.nota) <= 1 and 0 <= destino <= 127:
                nueva = replace(nota, nota=destino)
                confirmadas.add((nueva.nota, nueva.inicio))
                if nueva.nota != nota.nota:
                    # Recentrar el contorno para no sumar la corrección dos veces.
                    nueva = replace(nueva, pitch_bends=tuple(b + nota.nota - destino for b in nota.pitch_bends))
                    ajustes.append(AjusteAltura(inicio=round(nota.inicio, 4), original=nota.nota,
                                               corregida=destino, motivo="Altura estable confirmada en el audio"))
        resultado.append(nueva)
    informe = InterpretacionTarareo(
        afinacionReferenciaCents=round(referencia * 100, 2), notasVerificadas=len(confirmadas), ajustes=ajustes,
        motivo="Segunda opinión acústica sobre notas estables; sin imponer una escala ni buscar canciones.",
    )
    return resultado, confirmadas, informe
