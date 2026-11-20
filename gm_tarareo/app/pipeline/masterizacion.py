"""Acabado ligero del render, antes de normalizar su volumen (etapa 8).

El mismo procesamiento se aplica en la medición y en la codificación: la
ganancia final se calcula sobre la señal ya ecualizada y comprimida. Se
procesan ambos canales juntos para conservar el panorama de la mezcla.

El ambiente se ajusta en FluidSynth, donde ya existe una reverb por envío.
No se añade otro eco encima de toda la canción: taparía la melodía.
"""

from __future__ import annotations

PERFIL_MASTERIZACION = "suave-v1"

# Valores discretos, comunes a los 7 estilos. No cambian notas ni estructura.
# Paso alto: elimina subgraves bajo 30 Hz; el bajo musical sigue presente.
# EQ: -1.2 dB en graves medios y +0.6 dB en presencia, bandas anchas.
# Compresor RMS: umbral -30 dBFS antes de normalizar, ratio 1.3:1,
# rodilla suave, ataque de 30 ms y recuperación de 200 ms. Sin auto-ganancia.
# link=maximum aplica la misma reducción a ambos canales, sin mover el estéreo.
FILTROS_MASTERIZACION = (
    "highpass=f=30:p=2",
    "equalizer=f=280:t=o:w=1:g=-1.2",
    "equalizer=f=2800:t=o:w=1:g=0.6",
    ("acompressor=threshold=0.03162278:ratio=1.3:attack=30:release=200:"
     "knee=2.82843:makeup=1:link=maximum:detection=rms"),
)

# Reverb por envío de FluidSynth: menos húmeda que su configuración por
# defecto. Se dejan chorus, panorama y volúmenes de las pistas tal como están.
AMBIENTE_FLUIDSYNTH = {
    "synth.reverb.active": "1",
    "synth.reverb.level": "0.18",
    "synth.reverb.room-size": "0.30",
    "synth.reverb.damp": "0.55",
}


def filtros_masterizacion(activada: bool) -> list[str]:
    """Filtros para cada pasada de ffmpeg, o ninguno para comparar sin acabado."""
    return list(FILTROS_MASTERIZACION) if activada else []


def opciones_ambiente(activada: bool) -> list[str]:
    """Argumentos de FluidSynth; desactivada conserva su comportamiento anterior."""
    return [opcion for clave, valor in AMBIENTE_FLUIDSYNTH.items()
            for opcion in ("-o", f"{clave}={valor}")] if activada else []
