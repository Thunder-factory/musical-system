"""
Núcleo del worker: `ejecutar_job(solicitud) -> ResultadoJob`.

No conoce el transporte (decisión 5 de docs/ARQUITECTURA.md): no sabe de
FastAPI, del dict de jobs en memoria ni del callback. Recibe el sobre del
job, corre el pipeline y devuelve el resultado; nunca lanza.

Así, el adaptador HTTP de main.py es una de varias formas de llamarlo. Si
el equipo elige Celery u otra cola para hablar con los workers, se escribe
otro adaptador que llame a esta misma función, y el pipeline no se toca.
También permite probar el job completo sin levantar un servidor.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.almacenamiento import subir_salidas
from app.config import Configuracion
from app.modelos import (
    AnalisisMelodia,
    ArregloCancion,
    CodigoError,
    EstadoJob,
    RenderCancion,
    ResultadoJob,
    SolicitudProcesar,
    VersionCancion,
)
from app.pipeline.analisis import analizar
from app.pipeline.armonia import armonizar
from app.pipeline.arreglo import arreglar
from app.pipeline.clima import inferir_clima
from app.pipeline.estilo import inferir_estilo
from app.pipeline.excepciones import ErrorPipeline
from app.pipeline.expresion import conservar_expresion, expresar_arreglo
from app.pipeline.ingesta import ingestar, obtener_archivo_local
from app.pipeline.grafico import contorno, datos_grafico
from app.pipeline.interpretacion import medir_alturas, verificar_alturas
from app.pipeline.limpieza import limpiar_notas
from app.pipeline.melodia import extraer_melodia
from app.pipeline.muestras import recortar_muestra
from app.pipeline.partitura import escribir_partitura
from app.pipeline.preprocesado import preprocesar
from app.pipeline.render import renderizar
from app.pipeline.salida import escribir_analisis, escribir_arreglo_midi, escribir_midi

logger = logging.getLogger(__name__)

# (progreso 0-100, etapa[, salidas ya entregadas]) → None. Lo provee el
# adaptador: main.py lo usa para GET /jobs/{id} y para los callbacks de
# progreso. Cuando una versión de la canción está lista, se llama con las
# salidas entregadas hasta ese momento (así el usuario ya puede escucharla).
ReportarProgreso = Callable[..., None]

# Progreso al EMPEZAR cada etapa. melodía arranca en 15 y limpieza en 45
# porque basic-pitch es, lejos, la etapa más lenta; después vienen el render de
# la versión principal y, si hay, las alternativas.
PROGRESO_POR_ETAPA = {
    "ingesta": 5,
    "preprocesado": 10,
    "melodia": 15,
    "limpieza": 45,
    "analisis": 48,
    "armonia": 51,
    "estilo": 54,
    "arreglo": 56,
    "salida": 58,
    "render": 60,
    "alternativa-2": 74,
    "alternativa-3": 87,
}
# Progreso cuando cada versión ya está lista (y subida): la 1 es la principal.
PROGRESO_VERSION_LISTA = {1: 70, 2: 84, 3: 97}

VersionLista = Callable[[int, dict[str, Path]], None]


def _nombres_version(numero: int) -> tuple[str, str]:
    """Archivos de cada versión (la 1 incluye además melodia.mid y analisis.json)."""
    return ("cancion.mp3", "arreglo.mid") if numero == 1 else (f"cancion-{numero}.mp3", f"arreglo-{numero}.mid")


@dataclass(frozen=True)
class SalidaPipeline:
    analisis: AnalisisMelodia
    ruta_audio_preprocesado: Path
    archivos: dict[str, Path]  # nombre de salida → ruta, de todas las versiones generadas

    @property
    def ruta_cancion(self) -> Path:
        return self.archivos["cancion.mp3"]

    @property
    def ruta_midi(self) -> Path:
        return self.archivos["melodia.mid"]

    @property
    def ruta_arreglo(self) -> Path:
        return self.archivos["arreglo.mid"]

    @property
    def ruta_analisis(self) -> Path:
        return self.archivos["analisis.json"]


def _sin_reporte(*_args) -> None:
    return None


def _generar_version(numero: int, preset: str, analisis_musical, armonia, estilo, directorio: Path,
                     config: Configuracion, muestra: bool = False
                     ) -> tuple[VersionCancion, ArregloCancion, RenderCancion, dict[str, Path]]:
    """Arreglo + MIDI + render de una versión en el estilo `preset`."""
    estilo_version = estilo if preset == estilo.preset else estilo.model_copy(update={"preset": preset})
    resultado_arreglo = arreglar(analisis_musical, armonia, estilo_version,
                                 con_estribillo=config.arreglo_con_estribillo,
                                 variedad_ritmica=config.arreglo_variedad_ritmica,
                                 clima=inferir_clima(estilo.rasgos) if config.arreglo_clima_musical else None,
                                 instrumentacion_ampliada=config.arreglo_instrumentacion_ampliada)
    if config.melodia_expresiva:
        resultado_arreglo = expresar_arreglo(resultado_arreglo, analisis_musical, armonia)
    nombre_cancion, nombre_arreglo = _nombres_version(numero)
    ruta_arreglo = directorio / nombre_arreglo
    escribir_arreglo_midi(resultado_arreglo, ruta_arreglo)
    para_render, midi_render, config_render = resultado_arreglo, ruta_arreglo, config
    if muestra:
        nombre_cancion = "muestra.mp3" if numero == 1 else f"muestra-{numero}.mp3"
        para_render = recortar_muestra(resultado_arreglo, config.muestra_segundos)
        midi_render = directorio / f"_muestra-{numero}.mid"
        escribir_arreglo_midi(para_render, midi_render)
        config_render = config.model_copy(update={"render_cola_segundos": 0.4})
    try:
        ruta_cancion, render = renderizar(
            midi_render, directorio, para_render.arreglo.duracionSegundos, config_render,
            metadatos={"title": f"Tarareo → Canción ({preset})", "genre": preset, "comment": estilo.motivo},
            nombre=nombre_cancion,
        )
    finally:
        if muestra:
            midi_render.unlink(missing_ok=True)
    version = VersionCancion(
        numero=numero, estilo=preset, puntaje=estilo.puntajes.get(preset, 0.0),
        variante=resultado_arreglo.arreglo.variante, cancion=nombre_cancion, arreglo=nombre_arreglo,
        duracionSegundos=render.duracionSegundos, loudnessLufs=render.loudnessLufs,
        tipo="muestra" if muestra else "completa",
        duracionCompletaSegundos=round(resultado_arreglo.arreglo.duracionSegundos + config.render_cola_segundos, 2),
    )
    return version, resultado_arreglo.arreglo, render, {nombre_cancion: ruta_cancion, nombre_arreglo: ruta_arreglo}


def procesar_audio(
    ruta_entrada: Path,
    directorio: Path,
    config: Configuracion,
    avanzar: Callable[[str], None] = lambda _etapa: None,
    version_lista: VersionLista = lambda _numero, _archivos: None,
    muestras: bool = False,
) -> SalidaPipeline:
    """
    La secuencia de etapas sobre un archivo local, desde ffmpeg hasta escribir
    las salidas. Lanza ErrorPipeline si el audio no sirve.

    Es la única definición del orden de las etapas: la usan `ejecutar_job`
    (el worker) y `probar.py` (pruebas locales), así no pueden divergir.
    `avanzar(etapa)` se llama al empezar cada etapa, a partir de preprocesado
    (la ingesta la reporta quien también descarga el archivo).

    Versiones: primero se termina la PRINCIPAL (estilo mejor puntuado) y se
    avisa con `version_lista(1, archivos)` para entregarla ya. Después se
    generan hasta 2 alternativas en otros estilos que también encajan y se
    avisa cada una. Si una alternativa falla, la principal ya está entregada:
    se registra y se sigue.
    """
    wav = ingestar(ruta_entrada, directorio, config.frecuencia_muestreo_hz)

    avanzar("preprocesado")
    wav_preprocesado, duracion = preprocesar(wav, directorio, config)

    avanzar("melodia")
    notas_crudas, confianza = extraer_melodia(wav_preprocesado, config)

    avanzar("limpieza")
    interpretacion, confirmadas = None, set()
    medidas = _medir_alturas_seguro(wav_preprocesado)
    if config.interpretacion_verificar_alturas:
        notas_crudas, confirmadas, interpretacion = verificar_alturas(wav_preprocesado, notas_crudas, medidas)
    notas_finales, notas_descartadas = limpiar_notas(notas_crudas, config, confirmadas)
    if config.melodia_expresiva:
        conservar_expresion(notas_finales, notas_crudas, config.expresion_intensidad)

    avanzar("analisis")
    analisis_musical = analizar(notas_finales, wav_preprocesado, config)

    grafico = datos_grafico(contorno(*medidas[:3]) if medidas else [], notas_finales, analisis_musical)

    avanzar("armonia")
    armonia = armonizar(analisis_musical.melodiaCuantizada, analisis_musical.tonalidad)

    avanzar("estilo")
    estilo = inferir_estilo(notas_finales, analisis_musical)

    avanzar("arreglo")
    avanzar("salida")
    ruta_midi = directorio / "melodia.mid"
    escribir_midi(analisis_musical.melodiaCuantizada, ruta_midi, tempo=analisis_musical.bpm)
    ruta_partitura = directorio / "partitura.musicxml"
    escribir_partitura(analisis_musical, armonia, ruta_partitura)

    alternativas = list(enumerate(estilo.alternativas[: config.versiones_maximas - 1], start=2))
    hilos = min(len(alternativas), config.versiones_paralelas - 1)
    # Las alternativas arrancan YA, en paralelo con la principal. La principal
    # se sigue entregando primero; cada alternativa, apenas termina.
    pool = ThreadPoolExecutor(max_workers=hilos, thread_name_prefix="version") if hilos > 0 else None
    futuros = {
        pool.submit(_generar_version, numero, preset, analisis_musical, armonia, estilo,
                    directorio, config, muestra=muestras): (numero, preset)
        for numero, preset in alternativas
    } if pool else {}

    try:
        return _entregar_versiones(
            futuros, alternativas, estilo, analisis_musical, armonia, directorio, config, muestras,
            avanzar, version_lista, notas_finales, confianza, duracion, notas_crudas, notas_descartadas,
            interpretacion, ruta_midi, ruta_partitura, wav_preprocesado, grafico,
        )
    finally:
        if pool:
            pool.shutdown(wait=True, cancel_futures=True)


def _medir_alturas_seguro(ruta: Path):
    """La curva es un extra (gráfico + verificación): si falla, el tarareo sigue."""
    try:
        return medir_alturas(ruta)
    except Exception:
        logger.exception("No se pudo medir la curva de alturas de %s", ruta)
        return None


def _entregar_versiones(futuros, alternativas, estilo, analisis_musical, armonia, directorio, config,
                        muestras, avanzar, version_lista, notas_finales, confianza, duracion, notas_crudas,
                        notas_descartadas, interpretacion, ruta_midi, ruta_partitura, wav_preprocesado,
                        grafico=None) -> SalidaPipeline:
    """Genera la principal en este hilo, la entrega, y después entrega las alternativas."""
    avanzar("render")
    principal, arreglo, render, archivos_principal = _generar_version(
        1, estilo.preset, analisis_musical, armonia, estilo, directorio, config, muestra=muestras)

    analisis = AnalisisMelodia(
        melodia=notas_finales,
        confianza=confianza,
        duracionAudioSegundos=duracion,
        notasCrudas=len(notas_crudas),
        notasFinales=len(notas_finales),
        notasDescartadas=notas_descartadas,
        interpretacion=interpretacion,
        analisis=analisis_musical,
        armonia=armonia,
        estilo=estilo,
        arreglo=arreglo,
        render=render,
        versiones=[principal],
        grafico=grafico,
    )
    ruta_analisis = directorio / "analisis.json"
    escribir_analisis(analisis, ruta_analisis)
    archivos = {principal.cancion: archivos_principal[principal.cancion], "melodia.mid": ruta_midi,
                "arreglo.mid": archivos_principal["arreglo.mid"], "partitura.musicxml": ruta_partitura,
                "analisis.json": ruta_analisis}
    version_lista(1, dict(archivos))

    def entregar(numero: int, preset: str, generar) -> None:
        avanzar(f"alternativa-{numero}")
        try:
            version, _, _, archivos_version = generar()
        except Exception:
            logger.exception("No se pudo generar la versión %d (%s); la principal ya está entregada", numero, preset)
            return
        analisis.versiones.append(version)
        analisis.versiones.sort(key=lambda v: v.numero)
        escribir_analisis(analisis, ruta_analisis)
        archivos.update(archivos_version)
        version_lista(numero, {**archivos_version, "analisis.json": ruta_analisis})

    if futuros:
        # Ya se están generando a la vez; se entregan en orden de número para que
        # el progreso nunca retroceda (la 2 y la 3 terminan casi juntas). Solo este
        # hilo escribe analisis.json.
        for futuro, (numero, preset) in futuros.items():
            entregar(numero, preset, futuro.result)
    else:
        for numero, preset in alternativas:
            entregar(numero, preset, lambda numero=numero, preset=preset: _generar_version(
                numero, preset, analisis_musical, armonia, estilo, directorio, config, muestra=muestras))

    return SalidaPipeline(analisis, wav_preprocesado, archivos)


def completar_desde_analisis(ruta: Path, directorio: Path, numero: int, config,
                            version_lista: VersionLista) -> SalidaPipeline:
    """El análisis guardado (local o GET de R2) evita volver a ejecutar la IA."""
    try:
        analisis = AnalisisMelodia.model_validate_json(ruta.read_text(encoding="utf-8"))
        elegida = next(v for v in analisis.versiones if v.numero == numero)
    except (ValidationError, ValueError, StopIteration) as exc:
        raise ErrorPipeline("No existe esa versión en el análisis guardado.", CodigoError.ENTRADA_INVALIDA) from exc
    directorio.mkdir(parents=True, exist_ok=True)
    version, arreglo, render, archivos = _generar_version(
        numero, elegida.estilo, analisis.analisis, analisis.armonia, analisis.estilo, directorio, config,
    )
    analisis.arreglo, analisis.render, analisis.versiones = arreglo, render, [version]
    escribir_midi(analisis.analisis.melodiaCuantizada, directorio / "melodia.mid", tempo=analisis.analisis.bpm)
    escribir_partitura(analisis.analisis, analisis.armonia, directorio / "partitura.musicxml")
    escribir_analisis(analisis, directorio / "analisis.json")
    archivos.update({n: directorio / n for n in ("melodia.mid", "partitura.musicxml", "analisis.json")})
    version_lista(numero, archivos)
    return SalidaPipeline(analisis, ruta, archivos)


def ejecutar_job(
    solicitud: SolicitudProcesar,
    config: Configuracion,
    reportar_progreso: ReportarProgreso | None = None,
) -> ResultadoJob:
    """
    Corre las etapas implementadas para un job y devuelve su resultado final.

    Nunca lanza: cualquier error termina en un ResultadoJob FALLIDO con un
    mensaje accionable (restricción 6 de CLAUDE.md). Un error del reporte de
    progreso tampoco puede tumbar el job: es una notificación, no una
    dependencia.
    """
    job_id = solicitud.jobId
    directorio = config.directorio_job(job_id)
    reportar = reportar_progreso or _sin_reporte

    etapa_actual = ["ingesta"]  # lista: la modifica la función de abajo

    def avanzar(etapa: str) -> None:
        etapa_actual[0] = etapa
        logger.info("Job %s: etapa %s", job_id, etapa)
        try:
            reportar(PROGRESO_POR_ETAPA[etapa], etapa)
        except Exception:
            logger.exception("Job %s: falló el reporte de progreso de la etapa %s", job_id, etapa)

    urls: dict[str, str] = {}  # nombre de salida → URL entregada (sin firma) o ruta local

    def version_lista(numero: int, archivos: dict[str, Path]) -> None:
        """Entrega una versión apenas está: la sube (si Django pidió esos archivos) y avisa."""
        if solicitud.outputUploadUrls:
            pedidos = {n: u for n, u in solicitud.outputUploadUrls.items() if n in archivos}
            if pedidos:
                urls.update(zip(pedidos, subir_salidas(archivos, pedidos, config), strict=True))
        else:
            urls.update({n: str(r) for n, r in archivos.items()})  # desarrollo: rutas locales
        etapa_actual[0] = f"version-{numero}-lista"
        try:
            reportar(PROGRESO_VERSION_LISTA[numero], etapa_actual[0], list(urls.values()))
        except Exception:
            logger.exception("Job %s: falló el aviso de la versión %d", job_id, numero)

    try:
        avanzar("ingesta")
        ruta_entrada = obtener_archivo_local(solicitud.inputUrls[0], directorio, config)
        if solicitud.operacion == "completar":
            avanzar("arreglo")
            salida = completar_desde_analisis(ruta_entrada, directorio, solicitud.versionElegida, config, version_lista)
        else:
            salida = procesar_audio(ruta_entrada, directorio, config, avanzar, version_lista,
                                    muestras=solicitud.operacion == "muestras")
        if solicitud.outputUploadUrls:
            # Todo lo pedido ya está en R2: la copia local sobra (deuda técnica 4).
            shutil.rmtree(directorio, ignore_errors=True)

        analisis = salida.analisis
        logger.info("Job %s completado: %d notas finales, %d versión(es)", job_id, analisis.notasFinales,
                    len(analisis.versiones))
        return ResultadoJob(
            jobId=job_id,
            estado=EstadoJob.COMPLETADO,
            progreso=100,
            etapa="completado",
            outputUrls=list(urls.values()),
            metadatos={
                "notasFinales": analisis.notasFinales,
                "confianza": analisis.confianza,
                "bpm": analisis.analisis.bpm,
                "tonalidad": analisis.analisis.tonalidad,
                "acordes": analisis.armonia.acordes,
                "estilo": analisis.versiones[0].estilo,
                "estiloMensaje": analisis.estilo.mensaje,
                "estiloAmbiguo": analisis.estilo.ambiguo,
                "clima": analisis.arreglo.clima.model_dump() if analisis.arreglo.clima else None,
                "variante": analisis.arreglo.variante,
                "duracionCancionSegundos": analisis.render.duracionSegundos,
                "loudnessLufs": analisis.render.loudnessLufs,
                "grafico": analisis.grafico.model_dump() if analisis.grafico else None,
                "versiones": [
                    {"numero": v.numero, "estilo": v.estilo, "variante": v.variante, "cancion": v.cancion,
                     "puntaje": v.puntaje, "tipo": v.tipo}
                    for v in analisis.versiones
                ],
            },
        )

    except ErrorPipeline as exc:
        motivo = getattr(exc, "motivo", None)
        logger.warning("Job %s falló en la etapa %s (%s%s): %s", job_id, etapa_actual[0], exc.codigo.value,
                       f", {motivo.value}" if motivo else "", exc.mensaje)
        return ResultadoJob(
            jobId=job_id, estado=EstadoJob.FALLIDO, progreso=100, etapa=etapa_actual[0],
            error=exc.mensaje, codigoError=exc.codigo,
            metadatos={"motivo": motivo.value} if motivo else None,
        )
    except Exception:
        logger.exception("Error inesperado procesando el job %s en la etapa %s", job_id, etapa_actual[0])
        return ResultadoJob(
            jobId=job_id, estado=EstadoJob.FALLIDO, progreso=100, etapa=etapa_actual[0],
            error="Error interno inesperado procesando el audio.", codigoError=CodigoError.ERROR_INTERNO,
        )
