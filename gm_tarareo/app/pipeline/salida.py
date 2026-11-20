"""
Persistencia de los resultados: melodia.mid y analisis.json.

No es una etapa del pipeline técnico (que va de INGESTA a RENDER), es el
paso final de "volcar a disco lo que ya calculamos" — separado de main.py
porque escribir archivos es una responsabilidad del pipeline, no del
endpoint HTTP.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.modelos import AnalisisMelodia, NotaCuantizada
from app.pipeline.arreglo import ResultadoArreglo

TEMPO_MIDI_POR_DEFECTO = 120.0

# Mezcla de arreglo.mid: (volumen CC7 0-127, panorama CC10 0=izq 64=centro 127=der).
# La melodía adelante y al centro; la segunda voz más baja y a la derecha; el
# acompañamiento a la izquierda para que no tape la melodía; el colchón atrás.
# Es lo que FluidSynth respeta al renderizar (etapa 8).
# Ajustado 2026-11-14 tras la primera escucha ("que se escuche más claro el
# tarareo"): la melodía sube ~1 dB y el resto baja ~2-3 dB (en GM, el
# volumen CC7 cae 40·log10(v/127) dB), o sea ~4 dB más de diferencia.
CC_VOLUMEN, CC_PANORAMA = 7, 10
MEZCLA_POR_ROL = {
    "melodia": (120, 64),
    "segunda": (72, 84),
    "acompanamiento": (72, 44),
    "bajo": (90, 64),
    "colchon": (56, 64),
    "bateria": (80, 64),
    "color1": (54, 34),
    "color2": (50, 96),
}


def escribir_midi(notas: list[NotaCuantizada], ruta_salida: Path, tempo: float = TEMPO_MIDI_POR_DEFECTO) -> None:
    """
    Escribe la melodía ya puesta en tiempo (etapa 5) a un MIDI de una pista.

    Se escribe desde las posiciones en pulsos, no desde los segundos del
    audio: así, al abrir el archivo en un editor con el tempo `tempo`, las
    notas caen en la grilla de compases. Esto importa sobre todo cuando el
    tarareo era de ritmo libre: los segundos originales no encajarían en
    ningún tempo. El timing cantado sigue en `melodia` del analisis.json.
    """
    import pretty_midi

    segundos_por_pulso = 60.0 / tempo
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    instrumento = pretty_midi.Instrument(program=0)  # piano acústico, placeholder hasta la etapa de ARREGLO
    for nota in notas:
        inicio = nota.inicioPulsos * segundos_por_pulso
        instrumento.notes.append(
            pretty_midi.Note(
                velocity=nota.velocidad,
                pitch=nota.nota,
                start=inicio,
                end=inicio + nota.duracionPulsos * segundos_por_pulso,
            )
        )
    midi.instruments.append(instrumento)

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(ruta_salida))


def escribir_arreglo_midi(resultado: ResultadoArreglo, ruta_salida: Path) -> None:
    """
    Escribe la canción de la etapa 7 como MIDI multipista (General MIDI).

    Una pista por rol, con su programa GM; la batería va en el canal 10
    (is_drum), como manda el estándar. Se abre en cualquier editor o DAW.
    """
    import pretty_midi

    arreglo = resultado.arreglo
    segundos_por_pulso = 60.0 / arreglo.bpm
    midi = pretty_midi.PrettyMIDI(initial_tempo=arreglo.bpm)
    instrumentos = {}
    for pista in arreglo.pistas:
        instrumento = pretty_midi.Instrument(program=pista.programa, is_drum=pista.bateria, name=pista.nombre)
        volumen, panorama = MEZCLA_POR_ROL.get(pista.rol, (90, 64))
        instrumento.control_changes += [
            pretty_midi.ControlChange(number=CC_VOLUMEN, value=volumen, time=0.0),
            pretty_midi.ControlChange(number=CC_PANORAMA, value=panorama, time=0.0),
        ]
        instrumentos[pista.rol] = instrumento
        midi.instruments.append(instrumento)

    for e in resultado.eventos:
        instrumento = instrumentos.get(e.pista)
        if instrumento is None:
            continue
        inicio = e.inicio * segundos_por_pulso
        instrumento.notes.append(pretty_midi.Note(
            velocity=e.velocidad, pitch=int(np.clip(e.nota, 0, 127)),
            start=inicio, end=inicio + e.duracion * segundos_por_pulso,
        ))
        if e.expresion and e.pista == "melodia":
            for posicion, semitonos in e.expresion:
                # Rango GM ±2 semitonos. Resetear antes de la nota siguiente.
                t = inicio + posicion * e.duracion * segundos_por_pulso
                if posicion == 1:
                    t = max(inicio, t - 0.00001)
                instrumento.pitch_bends.append(pretty_midi.PitchBend(
                    pitch=int(np.clip(round(semitonos * 4096), -1434, 1434)), time=t,
                ))

    for instrumento in midi.instruments:
        if instrumento.pitch_bends:
            # RPN 0: rango de pitch bend explícito; no depender del sintetizador.
            instrumento.control_changes.extend(pretty_midi.ControlChange(number=n, value=v, time=0)
                for n, v in ((101, 0), (100, 0), (6, 2), (38, 0), (101, 127), (100, 127)))

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(ruta_salida))


def escribir_analisis(analisis: AnalisisMelodia, ruta_salida: Path) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta_salida.with_suffix(".json.tmp")
    temporal.write_text(analisis.model_dump_json(indent=2), encoding="utf-8")
    temporal.replace(ruta_salida)  # nunca servir un JSON a medio escribir
