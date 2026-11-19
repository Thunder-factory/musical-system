"""
Etapa 8 del pipeline: RENDER.

arreglo.mid → audio con instrumentos reales → volumen de plataforma → MP3.

1. FluidSynth (línea de comandos, igual que ffmpeg: sin dependencias de
   Python) sintetiza el MIDI con un SoundFont General MIDI. Determinista y
   en CPU: ~1-2 s para una canción de 80 s.
2. Acabado ligero: reverb moderada en FluidSynth, EQ suave y compresor
   estéreo en ffmpeg (se puede desactivar con TARAREO_RENDER_MASTERIZACION).
3. ffmpeg recorta la cola de la reverb, hace un fade-out y lleva el volumen
   a -16 LUFS con picos ≤ -1 dBTP: mide con `ebur128` y aplica la ganancia
   exacta + un limitador de seguridad (más rápido que `loudnorm` en dos
   pasadas). La compresión del paso anterior es independiente de la ganancia.
4. Se codifica a MP3 192 kbps con metadatos.

Restricción 7: el SoundFont tiene que permitir uso comercial. Se registra
cuál se usó y su licencia en el analisis.json.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

from app.modelos import RenderCancion
from app.pipeline.excepciones import ErrorRender
from app.pipeline.masterizacion import (
    PERFIL_MASTERIZACION,
    filtros_masterizacion,
    opciones_ambiente,
)

logger = logging.getLogger(__name__)

NOMBRE_MP3 = "cancion.mp3"
FRECUENCIA_RENDER_HZ = 44100
MARGEN_LIMITADOR_DB = 0.5

# Licencias verificadas de SoundFonts conocidos (restricción 7). Un SoundFont
# que no esté acá se puede usar, pero queda marcado para revisar.
LICENCIAS_SOUNDFONT = {
    "FluidR3_GM.sf2": "MIT (Frank Wen, 2000-2008). Verificada 2026-11-14 en el paquete Debian fluid-soundfont-gm",
    "MuseScore_General_Full.sf3": (
        "MIT, partes PD/CC0 (S. Christian Collins, deriva de FluidR3). Verificada 2026-11-14 "
        "en el paquete Debian musescore-general-soundfont 0.2.1"
    ),
}
LICENCIA_DESCONOCIDA = "DESCONOCIDA: verificar que permita uso comercial antes de producción"


# ----------------------------------------------------------------------------
# Herramientas
# ----------------------------------------------------------------------------

def resolver_fluidsynth(config) -> str:
    """
    Ruta a FluidSynth. Si está configurado, se usa eso (y si no existe es un
    error). Si no, se busca en herramientas/ (desarrollo local) y en el PATH.
    """
    if config.fluidsynth:
        encontrado = shutil.which(config.fluidsynth) or (config.fluidsynth if Path(config.fluidsynth).is_file() else None)
        if not encontrado:
            raise ErrorRender(
                f"No se encontró FluidSynth en '{config.fluidsynth}' (TARAREO_FLUIDSYNTH). "
                "Es un problema de configuración del servidor, no del tarareo."
            )
        return encontrado

    locales = sorted(config.directorio_herramientas.glob("fluidsynth/**/bin/fluidsynth*"))
    encontrado = str(locales[-1]) if locales else shutil.which("fluidsynth")
    if not encontrado:
        raise ErrorRender(
            "FluidSynth no está instalado: no se puede producir el audio final. Configurá "
            "TARAREO_FLUIDSYNTH o dejalo en herramientas/fluidsynth/. Es un problema del "
            "servidor, no del tarareo."
        )
    return encontrado


def resolver_soundfont(config) -> Path:
    """Ruta al SoundFont, con la misma lógica que `resolver_fluidsynth`."""
    if config.soundfont:
        if not Path(config.soundfont).is_file():
            raise ErrorRender(
                f"No se encontró el SoundFont '{config.soundfont}' (TARAREO_SOUNDFONT). "
                "Es un problema de configuración del servidor, no del tarareo."
            )
        return Path(config.soundfont)

    locales = sorted(config.directorio_herramientas.glob("soundfonts/*.sf2"))
    if not locales:
        raise ErrorRender(
            "No hay un SoundFont configurado: no se puede producir el audio final. Configurá "
            "TARAREO_SOUNDFONT o dejá un .sf2 en herramientas/soundfonts/."
        )
    return locales[0]


def herramientas_disponibles(config) -> bool:
    """Para tests y diagnóstico: si se puede renderizar en esta máquina."""
    try:
        resolver_fluidsynth(config)
        resolver_soundfont(config)
        return True
    except ErrorRender:
        return False


def _ejecutar(comando: list[str], que: str) -> subprocess.CompletedProcess:
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", check=False)
    except FileNotFoundError as exc:
        raise ErrorRender(f"No se pudo ejecutar {que}: {exc}") from exc
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout).strip().splitlines()[-1:] or ["sin detalle"]
        raise ErrorRender(f"Falló {que}: {detalle[0]}")
    return resultado


# ----------------------------------------------------------------------------
# Pasos
# ----------------------------------------------------------------------------

def sintetizar(ruta_midi: Path, ruta_wav: Path, config) -> Path:
    """arreglo.mid → WAV estéreo 44.1 kHz con FluidSynth."""
    fluidsynth = resolver_fluidsynth(config)
    soundfont = resolver_soundfont(config)
    _ejecutar(
        [fluidsynth, "-ni", "-q", "-g", str(config.render_ganancia), "-r", str(FRECUENCIA_RENDER_HZ),
         *opciones_ambiente(config.render_masterizacion),
         "-F", str(ruta_wav), str(soundfont), str(ruta_midi)],
        "FluidSynth",
    )
    if not ruta_wav.is_file() or ruta_wav.stat().st_size == 0:
        raise ErrorRender("FluidSynth terminó sin error pero no generó audio.")
    return soundfont


def _medidas_ebur128(salida_ffmpeg: str) -> tuple[float, float]:
    """(LUFS integrado, pico real en dBFS) del resumen que ebur128 imprime al final."""
    integrado = re.findall(r"\bI:\s+(-?[\d.]+|-inf) LUFS", salida_ffmpeg)
    pico = re.findall(r"\bPeak:\s+(-?[\d.]+|-inf) dBFS", salida_ffmpeg)
    if not integrado or not pico or "inf" in (integrado[-1], pico[-1]):
        raise ErrorRender("No se pudo medir el volumen del render (ebur128 no devolvió datos).")
    return float(integrado[-1]), float(pico[-1])


def normalizar_y_codificar(ruta_wav: Path, ruta_mp3: Path, duracion_musica: float, config,
                           metadatos: dict[str, str] | None = None) -> tuple[float, float]:
    """
    WAV → MP3 con fade-out y loudness de plataforma. Devuelve (LUFS, dBTP)
    medidos en la salida.

    `duracion_musica`: segundos hasta la última nota. Se deja sonar
    `render_cola_segundos` más (la reverb) y en ese tramo se hace el fade.

    Dos pasadas baratas en vez de `loudnorm` en dos pasadas (que tardaba
    ~10 s por canción en Docker, la mitad del job; medido 2026-11-14):
    1. Se aplica la masterización suave (si está activa) y `ebur128` mide el
       loudness integrado y el pico real de esa señal;
    2. se aplica la ganancia exacta que falta (lineal: no altera la dinámica)
       y un limitador que solo actúa si algún pico pasaría del máximo; en la
       misma pasada se codifica el MP3 y se vuelve a medir la salida.
    """
    cola = config.render_cola_segundos
    final = duracion_musica + cola
    # La medición y la codificación parten de la MISMA cadena. Procesar solo
    # después de medir haría incorrecta la ganancia calculada. El fade va al
    # final, así el compresor no vuelve a levantar la cola mientras se apaga.
    recorte = ",".join([
        f"atrim=0:{final:.3f}",
        *filtros_masterizacion(config.render_masterizacion),
        f"afade=t=out:st={duracion_musica:.3f}:d={max(cola, 0.01):.3f}",
    ])

    medicion = _ejecutar(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta_wav),
         "-af", f"{recorte},ebur128=peak=true", "-f", "null", "-"],
        "la medición de volumen (ffmpeg ebur128)",
    )
    lufs_entrada, _ = _medidas_ebur128(medicion.stderr)
    ganancia_db = config.render_lufs_objetivo - lufs_entrada
    # El limitador de ffmpeg trabaja sobre picos de muestra, no "true peak":
    # se le deja MARGEN_LIMITADOR_DB de aire para que el pico real quede bajo el máximo.
    techo = 10 ** ((config.render_pico_maximo_dbtp - MARGEN_LIMITADOR_DB) / 20)
    cadena = (f"{recorte},volume={ganancia_db:.2f}dB,"
              f"alimiter=limit={techo:.4f}:attack=5:release=50:level=disabled,ebur128=peak=true")

    etiquetas = []
    for clave, valor in (metadatos or {}).items():
        etiquetas += ["-metadata", f"{clave}={valor}"]
    codificacion = _ejecutar(
        ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(ruta_wav), "-af", cadena,
         "-ar", str(FRECUENCIA_RENDER_HZ), "-c:a", "libmp3lame", "-b:a", f"{config.render_bitrate_kbps}k",
         *etiquetas, str(ruta_mp3)],
        "la codificación a MP3 (ffmpeg)",
    )
    return _medidas_ebur128(codificacion.stderr)


def duracion_audio(ruta: Path) -> float:
    resultado = _ejecutar(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
        "ffprobe",
    )
    return float(resultado.stdout.strip())


# ----------------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------------

def renderizar(ruta_midi: Path, directorio: Path, duracion_musica: float, config,
               metadatos: dict[str, str] | None = None, nombre: str = NOMBRE_MP3) -> tuple[Path, RenderCancion]:
    """
    arreglo.mid → MP3 (`nombre`: cancion.mp3, o cancion-2.mp3 para una versión
    alternativa). Devuelve la ruta y el resumen para el analisis.json.
    """
    ruta_wav = directorio / f"render-{Path(nombre).stem}.wav"
    ruta_mp3 = directorio / nombre

    soundfont = sintetizar(ruta_midi, ruta_wav, config)
    lufs, pico = normalizar_y_codificar(ruta_wav, ruta_mp3, duracion_musica, config, metadatos)
    ruta_wav.unlink(missing_ok=True)  # intermedio pesado (~15 MB): ya está en el MP3

    licencia = LICENCIAS_SOUNDFONT.get(soundfont.name, LICENCIA_DESCONOCIDA)
    if licencia == LICENCIA_DESCONOCIDA:
        logger.warning("SoundFont %s sin licencia verificada (restricción 7 de CLAUDE.md)", soundfont.name)

    resumen = RenderCancion(
        archivo=ruta_mp3.name,
        duracionSegundos=round(duracion_audio(ruta_mp3), 2),
        loudnessLufs=round(lufs, 1),
        picoDbtp=round(pico, 1),
        bitrateKbps=config.render_bitrate_kbps,
        soundfont=soundfont.name,
        licenciaSoundfont=licencia,
        masterizacion=PERFIL_MASTERIZACION if config.render_masterizacion else "desactivada",
    )
    logger.info("Render listo: %s (%.1f s, %.1f LUFS, pico %.1f dBTP, %s)",
                ruta_mp3, resumen.duracionSegundos, lufs, pico, soundfont.name)
    return ruta_mp3, resumen
