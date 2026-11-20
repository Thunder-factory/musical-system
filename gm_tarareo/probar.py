"""
Corre el pipeline (ingesta -> preprocesado -> melodía -> limpieza ->
análisis) sobre uno o varios audios locales, sin levantar el servidor.

Es la herramienta para iterar rápido mientras se ajustan los umbrales de
config.py contra tarareos reales. Usa la misma secuencia de etapas que el
worker (`app.nucleo.procesar_audio`).

Uso:
    (venv) python probar.py mi_audio.wav
    (venv) python probar.py mi_audio.m4a --salida salidas/mi_prueba
    (venv) python probar.py mi_audio.m4a --escucha   # + tarareo con metrónomo
    (venv) python probar.py --lote tests/audio --escucha
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import obtener_configuracion
from app.modelos import (
    AnalisisArmonia,
    AnalisisMusical,
    ArregloCancion,
    EstiloInferido,
    NotaDescartada,
    NotaMusical,
    RenderCancion,
)
from app.nucleo import procesar_audio
from app.pipeline.excepciones import ErrorAudioInvalido, ErrorPipeline

logger = logging.getLogger(__name__)

# Los mismos formatos que graban el navegador y el móvil (ver CLAUDE.md).
EXTENSIONES_AUDIO = (".wav", ".m4a", ".mp3", ".webm", ".ogg")


@dataclass
class ResultadoPrueba:
    """Resultado de correr el pipeline sobre un archivo, para un solo audio o para una fila de --lote."""

    archivo: str
    ok: bool
    tiempo_segundos: float
    notas_crudas: int = 0
    notas_finales: int = 0
    confianza: float = 0.0
    duracion_audio: float = 0.0
    motivo_fallo: str | None = None
    mensaje_error: str | None = None
    notas: list[NotaMusical] = field(default_factory=list)
    notas_descartadas: list[NotaDescartada] = field(default_factory=list)
    ruta_midi: Path | None = None
    ruta_analisis: Path | None = None
    ruta_escucha: Path | None = None
    analisis: AnalisisMusical | None = None
    armonia: AnalisisArmonia | None = None
    estilo: EstiloInferido | None = None
    arreglo: ArregloCancion | None = None
    render: RenderCancion | None = None
    ruta_cancion: Path | None = None


def generar_escucha(ruta_audio: Path, analisis: AnalisisMusical, ruta_salida: Path) -> None:
    """
    Escribe el tarareo con un metrónomo encima, al tempo y fase que entendió
    la etapa 5. Es la forma de validar el análisis sin saber "qué canción
    era": si el click acompaña el pulso que uno sintió al tararear, el tempo
    está bien entendido. El primer tiempo de cada compás suena más agudo.
    """
    audio, sr = sf.read(str(ruta_audio), dtype="float32", always_2d=False)
    pulso = 60.0 / analisis.bpm
    duracion_click = int(0.03 * sr)
    t = np.arange(duracion_click) / sr
    envolvente = np.exp(-t * 120)
    clicks = np.zeros_like(audio)

    tiempo = analisis.desfasePulsoSegundos
    while tiempo > 0:  # pulsos anteriores al pulso 0 (antes de la primera nota)
        tiempo -= pulso
    numero_pulso = round((tiempo - analisis.desfasePulsoSegundos) / pulso)
    while tiempo < len(audio) / sr:
        inicio = int(tiempo * sr)
        if inicio >= 0:
            frecuencia = 1600.0 if numero_pulso % 4 == 0 else 1000.0
            tramo = 0.5 * np.sin(2 * np.pi * frecuencia * t) * envolvente
            fin = min(len(audio), inicio + duracion_click)
            clicks[inicio:fin] += tramo[: fin - inicio]
        tiempo += pulso
        numero_pulso += 1

    mezcla = 0.8 * audio + clicks
    mezcla /= max(1.0, float(np.max(np.abs(mezcla))) / 0.95)
    sf.write(str(ruta_salida), mezcla, sr)


def generar_escucha_melodia(
    analisis: AnalisisMusical, ruta_salida: Path, armonia: AnalisisArmonia | None = None, sr: int = 22050,
) -> None:
    """
    Sintetiza la melodía YA PUESTA EN TIEMPO (melodiaCuantizada) con un tono
    simple y un metrónomo. Es lo que se escucha para juzgar la etapa 5: tienen
    que ser tus notas, en tu orden, ahora con pulso. Con `armonia`, además
    suenan los acordes de la etapa 6 de fondo (tono suave, octava grave).
    """
    pulso = 60.0 / analisis.bpm
    total_pulsos = max(n.inicioPulsos + n.duracionPulsos for n in analisis.melodiaCuantizada) + 1
    if armonia:
        total_pulsos = max(total_pulsos, max(a.inicioPulsos + a.duracionPulsos for a in armonia.progresion))
    audio = np.zeros(int(total_pulsos * pulso * sr) + sr, dtype=np.float32)

    for acorde in armonia.progresion if armonia else []:
        inicio = int(acorde.inicioPulsos * pulso * sr)
        largo = int(acorde.duracionPulsos * pulso * sr)
        t = np.arange(largo) / sr
        envolvente = np.minimum(1.0, t / 0.05) * np.minimum(1.0, (largo / sr - t) / 0.08)
        for nota in acorde.notas:
            frecuencia = 440.0 * 2 ** ((nota - 69) / 12)
            audio[inicio:inicio + largo] += (0.12 * np.sin(2 * np.pi * frecuencia * t) * envolvente).astype(np.float32)

    for n in analisis.melodiaCuantizada:
        inicio = int(n.inicioPulsos * pulso * sr)
        largo = int(n.duracionPulsos * pulso * sr)
        t = np.arange(largo) / sr
        frecuencia = 440.0 * 2 ** ((n.nota - 69) / 12)
        envolvente = np.minimum(1.0, t / 0.01) * np.exp(-t * 1.5) * np.minimum(1.0, (largo / sr - t) / 0.02)
        tono = 0.35 * (np.sin(2 * np.pi * frecuencia * t) + 0.3 * np.sin(4 * np.pi * frecuencia * t))
        audio[inicio:inicio + largo] += (tono * envolvente).astype(np.float32)

    t_click = np.arange(int(0.03 * sr)) / sr
    for numero in range(int(total_pulsos)):
        inicio = int(numero * pulso * sr)
        frecuencia = 1600.0 if numero % 4 == 0 else 1000.0
        click = 0.3 * np.sin(2 * np.pi * frecuencia * t_click) * np.exp(-t_click * 120)
        audio[inicio:inicio + len(click)] += click.astype(np.float32)

    audio /= max(1.0, float(np.max(np.abs(audio))) / 0.95)
    sf.write(str(ruta_salida), audio, sr)


def sintetizar_maqueta(ruta_midi: Path, ruta_salida: Path, sr: int = 22050) -> None:
    """
    Maqueta de `arreglo.mid` SIN FluidSynth: tonos simples para los
    instrumentos (pretty_midi) y ruido/tonos graves para la batería. Sirve
    para juzgar estructura, ritmo, acordes y batería, no el timbre de los
    instrumentos: eso llega con el render de la etapa 8.
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(ruta_midi))
    audio = np.zeros(int((midi.get_end_time() + 1.0) * sr), dtype=np.float32)
    rng = np.random.default_rng(0)

    for instrumento in midi.instruments:
        if instrumento.is_drum:
            for n in instrumento.notes:
                inicio = int(n.start * sr)
                largo = int(0.15 * sr)
                t = np.arange(largo) / sr
                if n.pitch in (36, 45):  # bombo / tom: tono grave que cae
                    golpe = np.sin(2 * np.pi * (110 - 60 * t / t[-1]) * t) * np.exp(-t * 25)
                elif n.pitch in (42, 46, 51, 54, 70):  # platillos chicos: ruido corto
                    golpe = 0.35 * rng.standard_normal(largo) * np.exp(-t * 60)
                else:  # caja, baqueta, platillo: ruido más largo
                    golpe = 0.6 * rng.standard_normal(largo) * np.exp(-t * 20)
                fin = min(len(audio), inicio + largo)
                audio[inicio:fin] += (golpe[: fin - inicio] * n.velocity / 127 * 0.5).astype(np.float32)
            continue
        tono = instrumento.synthesize(fs=sr)
        audio[: len(tono)] += 0.25 * tono[: len(audio)].astype(np.float32)

    audio /= max(1.0, float(np.max(np.abs(audio))) / 0.95)
    sf.write(str(ruta_salida), audio, sr)


def procesar_archivo(ruta_audio: Path, directorio_job: Path, config, escucha: bool = False) -> ResultadoPrueba:
    """Corre el pipeline sobre un archivo y devuelve el resultado (nunca lanza: los errores del pipeline quedan en el resultado)."""
    inicio = time.time()
    try:
        directorio_job.mkdir(parents=True, exist_ok=True)
        salida = procesar_audio(ruta_audio, directorio_job, config)
    except ErrorAudioInvalido as exc:
        return ResultadoPrueba(
            archivo=ruta_audio.name, ok=False, tiempo_segundos=time.time() - inicio,
            motivo_fallo=exc.motivo.value, mensaje_error=exc.mensaje,
        )
    except ErrorPipeline as exc:
        return ResultadoPrueba(
            archivo=ruta_audio.name, ok=False, tiempo_segundos=time.time() - inicio,
            mensaje_error=exc.mensaje,
        )

    a = salida.analisis
    ruta_escucha = None
    if escucha:
        ruta_escucha = directorio_job / "escucha_melodia.wav"
        generar_escucha_melodia(a.analisis, ruta_escucha)
        generar_escucha_melodia(a.analisis, directorio_job / "escucha_armonia.wav", a.armonia)
        sintetizar_maqueta(salida.ruta_arreglo, directorio_job / "escucha_arreglo.wav")
        if a.analisis.ritmo == "medido":
            # Solo tiene sentido si el tarareo tenía pulso: el click acompaña la grabación.
            generar_escucha(salida.ruta_audio_preprocesado, a.analisis, directorio_job / "escucha_metronomo.wav")

    return ResultadoPrueba(
        archivo=ruta_audio.name, ok=True, tiempo_segundos=time.time() - inicio,
        notas_crudas=a.notasCrudas, notas_finales=a.notasFinales,
        confianza=a.confianza, duracion_audio=a.duracionAudioSegundos,
        notas=a.melodia, notas_descartadas=a.notasDescartadas,
        ruta_midi=salida.ruta_midi, ruta_analisis=salida.ruta_analisis,
        ruta_escucha=ruta_escucha, analisis=a.analisis, armonia=a.armonia, estilo=a.estilo,
        arreglo=a.arreglo, render=a.render, ruta_cancion=salida.ruta_cancion,
    )


def imprimir_resultado_individual(r: ResultadoPrueba) -> None:
    if not r.ok:
        detalle = f" ({r.motivo_fallo})" if r.motivo_fallo else ""
        print(f"\nFALLÓ{detalle}: {r.mensaje_error}", file=sys.stderr)
        return

    print(f"\n{'=' * 58}")
    print(f"  {r.notas_crudas} notas crudas -> {r.notas_finales} finales "
          f"({len(r.notas_descartadas)} descartadas)")
    print(f"  confianza promedio: {r.confianza:.2f}   duración: {r.duracion_audio:.1f}s   "
          f"tiempo total: {r.tiempo_segundos:.1f}s")
    print(f"{'=' * 58}\n")
    for nota in r.notas:
        print(f"  nota={nota.nota:3d}  inicio={nota.inicio:6.2f}s  dur={nota.duracion:5.2f}s  vel={nota.velocidad:3d}")

    a = r.analisis
    print(f"\n  tempo: {a.bpm:.1f} BPM, ritmo {a.ritmo} (confianza {a.confianzaBpm:.2f}; librosa: {a.bpmLibrosa or 'sin dato'})")
    print(f"  {a.motivoRitmo}")
    print(f"  tonalidad: {a.tonalidad} (correlación {a.confianzaTonalidad:.2f})   compás: {a.compas}")
    ajustadas = sum(n.ajustada for n in a.melodiaCuantizada)
    print(f"  {ajustadas}/{len(a.melodiaCuantizada)} notas ajustadas a la grilla de semicorcheas")
    print(f"  acordes: {' | '.join(f'{x.nombre} ({x.grado})' for x in r.armonia.progresion)}"
          f"   anacrusa: {r.armonia.anacrusaPulsos:g} pulsos")
    print(f"  estilo: {r.estilo.preset} — {r.estilo.motivo}")
    print(f"  {r.estilo.mensaje} (confianza {r.estilo.confianza:.2f}, alternativa: {r.estilo.alternativa})")
    arr = r.arreglo
    print(f"  arreglo: variante {arr.variante}, {arr.duracionSegundos:.0f} s, "
          f"{' → '.join(s.nombre for s in arr.estructura)}")
    ren = r.render
    print(f"  render: {ren.duracionSegundos:.1f} s, {ren.loudnessLufs:.1f} LUFS, pico {ren.picoDbtp:.1f} dBTP, "
          f"{ren.bitrateKbps} kbps, SoundFont {ren.soundfont} ({ren.licenciaSoundfont.split('.')[0]})")

    print(f"\nMIDI:      {r.ruta_midi}")
    print(f"Análisis:  {r.ruta_analisis}")
    print(f"CANCIÓN:   {r.ruta_cancion}")
    if r.ruta_escucha:
        print(f"Escucha:   {r.ruta_escucha}  (tu melodía puesta en tiempo + metrónomo)")


COLUMNAS_ESTILOS = ("archivo", "preset", "confianza", "alternativa", "ambiguo",
                    "bpm", "modo", "densidad", "articulacion", "rango", "saltos", "repeticion")


def escribir_csv_estilos(resultados: list[ResultadoPrueba], ruta: Path) -> None:
    """
    Rasgos y estilo inferido de cada grabación, para calibrar la etapa 6.5.

    Para sumar una validación nueva: escuchar la canción, y si el estilo
    coincide con la sensación de quien tarareó, copiar la fila a
    tests/audio/estilos_validados.csv (columna `preset` = el estilo validado).
    """
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS_ESTILOS)
        for r in resultados:
            if not r.ok:
                continue
            e, x = r.estilo, r.estilo.rasgos
            escritor.writerow([r.archivo, e.preset, e.confianza, e.alternativa, e.ambiguo,
                               x.bpm, x.modo, x.densidad, x.articulacion, x.rango, x.saltos, x.repeticion])


def imprimir_tabla_lote(resultados: list[ResultadoPrueba], umbral_confianza: float) -> None:
    ancho_archivo = max(len(r.archivo) for r in resultados) if resultados else 8
    ancho_archivo = max(ancho_archivo, len("archivo"))

    encabezado = (
        f"{'archivo':<{ancho_archivo}}  {'crudas':>6}  {'finales':>7}  "
        f"{'confianza':>9}  {'bpm':>6}  {'ritmo':<6}  {'conf':>4}  {'tonalidad':<10}  {'estilo/variante':<20}  motivo / acordes"
    )
    print(encabezado)
    print("-" * len(encabezado))

    for r in resultados:
        crudas = str(r.notas_crudas) if r.ok else "-"
        finales = str(r.notas_finales) if r.ok else "-"
        confianza = f"{r.confianza:.3f}" if r.ok else "-"
        motivo = r.motivo_fallo or ""
        bpm = f"{r.analisis.bpm:.1f}" if r.analisis else "-"
        conf_bpm = f"{r.analisis.confianzaBpm:.2f}" if r.analisis else "-"
        tonalidad = r.analisis.tonalidad if r.analisis else "-"
        ritmo = r.analisis.ritmo if r.analisis else "-"
        estilo = f"{r.estilo.preset}/{r.arreglo.variante}" if r.estilo else "-"
        acordes = " ".join(r.armonia.acordes) if r.armonia else ""
        print(f"{r.archivo:<{ancho_archivo}}  {crudas:>6}  {finales:>7}  {confianza:>9}  "
              f"{bpm:>6}  {ritmo:<6}  {conf_bpm:>4}  {tonalidad:<10}  {estilo:<20}  {motivo}{acordes}")

    exitosos = [r for r in resultados if r.ok]
    fallidos = [r for r in resultados if not r.ok]
    print(f"\n{len(exitosos)}/{len(resultados)} con melodía válida (umbral de confianza: {umbral_confianza:.2f})")
    if exitosos:
        confianzas = [r.confianza for r in exitosos]
        print(f"  confianza (ok):     min={min(confianzas):.3f}  max={max(confianzas):.3f}  "
              f"promedio={sum(confianzas) / len(confianzas):.3f}")
    if fallidos:
        motivos_ruido = [r for r in fallidos if r.motivo_fallo == "SIN_MELODIA_CLARA"]
        print(f"  fallidos: {len(fallidos)} ({len(motivos_ruido)} por SIN_MELODIA_CLARA)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("audio", nargs="?", help="Ruta a un archivo de audio (no usar junto con --lote)")
    parser.add_argument("--lote", metavar="CARPETA", help="Procesa todos los audios de una carpeta y muestra una tabla comparativa")
    parser.add_argument("--escucha", action="store_true", help="Genera escucha_metronomo.wav: el tarareo con un click al tempo entendido")
    parser.add_argument("--salida", help="Carpeta de salida (default: salidas/prueba-<nombre> o salidas/lote-<carpeta>)")
    args = parser.parse_args()

    if not args.audio and not args.lote:
        parser.error("pasá un archivo de audio o --lote CARPETA")
    if args.audio and args.lote:
        parser.error("pasá un archivo de audio o --lote CARPETA, no los dos")

    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
    config = obtener_configuracion()

    if args.lote:
        carpeta = Path(args.lote)
        if not carpeta.is_dir():
            print(f"No es una carpeta: {carpeta}", file=sys.stderr)
            return 1

        archivos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXTENSIONES_AUDIO)
        if not archivos:
            print(f"No hay archivos de audio ({', '.join(EXTENSIONES_AUDIO)}) en {carpeta}", file=sys.stderr)
            return 1

        directorio_base = Path(args.salida) if args.salida else config.directorio_salidas / f"lote-{carpeta.name}"
        resultados = []
        for ruta_audio in archivos:
            logger.info("Procesando %s...", ruta_audio.name)
            # El nombre con extensión: "01 T.mp3" y "01 T.wav" no pueden compartir carpeta.
            directorio_job = directorio_base / ruta_audio.name.replace(".", "_")
            resultados.append(procesar_archivo(ruta_audio, directorio_job, config, args.escucha))

        print()
        imprimir_tabla_lote(resultados, config.melodia_confianza_minima)
        ruta_csv = directorio_base / "estilos.csv"
        escribir_csv_estilos(resultados, ruta_csv)
        print(f"\nEstilos y rasgos (para calibrar): {ruta_csv}")
        return 0 if any(r.ok for r in resultados) else 1

    ruta_audio = Path(args.audio)
    if not ruta_audio.exists():
        print(f"No existe el archivo: {ruta_audio}", file=sys.stderr)
        return 1

    directorio = Path(args.salida) if args.salida else config.directorio_salidas / f"prueba-{ruta_audio.stem}"
    resultado = procesar_archivo(ruta_audio, directorio, config, args.escucha)
    imprimir_resultado_individual(resultado)
    return 0 if resultado.ok else 1


if __name__ == "__main__":
    sys.exit(main())
