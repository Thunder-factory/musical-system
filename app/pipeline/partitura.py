"""Partitura MusicXML de la idea tarareada, con cifrado de acordes (music21)."""

from pathlib import Path


def escribir_partitura(analisis, armonia, ruta: Path) -> None:
    from music21 import harmony, key, metadata, meter, note, pitch, stream, tempo

    partitura = stream.Score()
    partitura.metadata = metadata.Metadata(title="Tu idea musical", composer="Tarareo → Canción")
    parte = stream.Part(id="melodia")
    tonica, modo = analisis.tonalidad.split()
    parte.insert(0, key.Key(tonica.replace("b", "-"), modo))
    parte.insert(0, meter.TimeSignature(analisis.compas))
    parte.insert(0, tempo.MetronomeMark(number=analisis.bpm))
    notas = sorted(analisis.melodiaCuantizada, key=lambda n: n.inicioPulsos)
    final_anterior = 0.0
    for i, n in enumerate(notas):
        # Solo la notación se redondea a semicorcheas. El MIDI conserva su
        # timing y expresión; evitar fracciones imposibles de imprimir.
        inicio = max(final_anterior, round(n.inicioPulsos * 4) / 4)
        duracion = max(0.25, round(n.duracionPulsos * 4) / 4)
        if i + 1 < len(notas):
            siguiente = round(notas[i + 1].inicioPulsos * 4) / 4
            if siguiente > inicio:
                duracion = min(duracion, siguiente - inicio)
        if inicio > final_anterior:
            parte.insert(final_anterior, note.Rest(quarterLength=inicio - final_anterior))
        parte.insert(inicio, note.Note(n.nota, quarterLength=duracion))
        final_anterior = inicio + duracion
    for a in armonia.progresion:
        raiz = pitch.Pitch()
        raiz.midi = a.notas[0]
        calidad = "" if (a.notas[1] - a.notas[0]) % 12 == 4 else "m"
        simbolo = harmony.ChordSymbol(raiz.name + calidad)
        parte.insert(round(a.inicioPulsos * 4) / 4, simbolo)
    partitura.insert(0, parte)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    partitura.write("musicxml", fp=str(ruta))
