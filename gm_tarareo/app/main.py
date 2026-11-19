"""
Adaptador HTTP (FastAPI) del worker de Tarareo -> Canción.

Solo traduce HTTP al núcleo (`app.nucleo.ejecutar_job`): valida la
solicitud, controla cuántos jobs corren a la vez, encola el trabajo pesado
en background y responde al instante (restricción 2 de CLAUDE.md, nunca
bloquea). Guarda el estado para GET /jobs/{id} y avisa al callback.

No hay nada de MIR acá. Si el equipo cambia HTTP por una cola, este archivo
se reemplaza por otro adaptador y el núcleo y el pipeline no se tocan.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.background import BackgroundTasks

from app.calentamiento import calentar
from app.capacidad import ControlCapacidad
from app.config import obtener_configuracion
from app.modelos import (
    EstadoJob,
    RespuestaProcesar,
    RespuestaSalud,
    ResultadoJob,
    SolicitudProcesar,
)
from app.nucleo import ejecutar_job
from app.pipeline.melodia import cargar_modelo, modelo_cargado
from app.reintentos import con_reintentos
from app.retencion import RegistroJobs, purgar_salidas

config = obtener_configuracion()
logging.basicConfig(level=config.nivel_log, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
# httpx registra en INFO cada request con la URL completa, y la de una URL
# prefirmada de R2 lleva la firma en la query: con ella cualquiera baja el
# archivo hasta que venza. Nuestros propios logs usan describir_url().
logging.getLogger("httpx").setLevel(logging.WARNING)

# Segundos que se le sugieren a Django para reintentar cuando el worker
# está lleno (header Retry-After del 503).
REINTENTAR_EN_SEGUNDOS = 10
ENCABEZADO_TOKEN = "X-Worker-Token"


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """
    Carga el modelo de basic-pitch UNA vez, antes de aceptar solicitudes.

    Antes se importaba TensorFlow la primera vez que alguien llamaba a
    /salud (congelaba el event loop ~20 s) y el modelo se recargaba en cada
    job. Se carga en un hilo aparte para no bloquear el event loop
    mientras arranca. Si falla, el worker no arranca: un worker sin modelo
    no sirve, y es mejor que Docker lo vea caído a que acepte jobs que
    van a fallar todos.
    """
    if config.modo_desarrollo:
        logger.warning(
            "TARAREO_MODO_DESARROLLO activo: se aceptan rutas locales en inputUrls. "
            "No usar así en producción."
        )
    await asyncio.to_thread(cargar_modelo)
    # Compila de antemano lo que librosa acelera con numba: si no, el primer
    # job después de cada arranque tardaba ~85 s de más (ver app/calentamiento.py).
    await asyncio.to_thread(calentar, config)
    logger.info("Modelo cargado. Worker listo (capacidad %d)", config.capacidad)
    yield


app = FastAPI(title="Worker Tarareo -> Canción", version=config.version, lifespan=ciclo_de_vida)

capacidad = ControlCapacidad(config.capacidad)

# Estado de jobs para GET /jobs/{id}, con límite de tiempo y de cantidad
# (deuda técnica 4, ver app/retencion.py). Si el worker se reinicia se pierde,
# igual que cualquier BackgroundTask en curso: lo cubre el timeout de Django
# (decisión 7 de docs/ARQUITECTURA.md).
trabajos = RegistroJobs(config.retencion_jobs_minutos * 60, config.maximo_jobs_en_memoria)


@app.get("/salud", response_model=RespuestaSalud)
async def salud() -> RespuestaSalud:
    return RespuestaSalud(
        version=config.version,
        modelosCargados=modelo_cargado(),
        capacidad=capacidad.capacidad,
        ocupados=capacidad.ocupados,
    )


@app.post(
    "/procesar",
    status_code=202,
    response_model=RespuestaProcesar,
    responses={503: {"description": "El worker está lleno; reintentar más tarde (ver Retry-After)"}},
)
async def procesar(solicitud: SolicitudProcesar, tareas: BackgroundTasks) -> RespuestaProcesar:
    job_id = solicitud.jobId

    # Idempotencia: si Django reenvía un job que todavía se está procesando
    # (por ejemplo, porque no le llegó el 202), no se arranca un segundo
    # proceso sobre la misma carpeta. Un job ya terminado sí se vuelve a
    # correr: ese reenvío es un reintento a propósito.
    existente = trabajos.get(job_id)
    if existente is not None and existente.estado == EstadoJob.PROCESANDO:
        logger.info("Job %s ya está en proceso; se ignora el reenvío", job_id)
        return RespuestaProcesar(jobId=job_id, estado=EstadoJob.PROCESANDO)

    if not capacidad.intentar_ocupar():
        logger.warning("Job %s rechazado: worker lleno (%d/%d)", job_id, capacidad.ocupados, capacidad.capacidad)
        raise HTTPException(
            status_code=503,
            detail=f"El worker está procesando {capacidad.capacidad} job(s), su máximo. Reintentar más tarde.",
            headers={"Retry-After": str(REINTENTAR_EN_SEGUNDOS)},
        )

    origen_local = None
    if config.modo_desarrollo and solicitud.operacion == "completar":
        origen_local = {"origenLocal": Path(solicitud.inputUrls[0]).parent.name}
    trabajos[job_id] = ResultadoJob(jobId=job_id, estado=EstadoJob.PROCESANDO, progreso=0, etapa="en cola",
                                   metadatos=origen_local)
    tareas.add_task(procesar_en_segundo_plano, solicitud)
    logger.info("Job %s encolado (%d archivo(s) de entrada, %s)", job_id, len(solicitud.inputUrls),
                "sube a R2" if solicitud.outputUploadUrls else "salidas locales")
    return RespuestaProcesar(jobId=job_id, estado=EstadoJob.PROCESANDO)


@app.get("/jobs/{job_id}", response_model=ResultadoJob)
async def obtener_job(job_id: UUID) -> ResultadoJob:
    resultado = trabajos.get(job_id)
    if resultado is None:
        raise HTTPException(status_code=404, detail=f"No existe un job con id '{job_id}'")
    return resultado


def procesar_en_segundo_plano(solicitud: SolicitudProcesar) -> None:
    """
    Corre el núcleo, guarda el resultado, avisa al callback y libera el cupo.

    Se ejecuta en el threadpool de BackgroundTasks (FastAPI lo hace solo
    para funciones sync), así que basic-pitch no bloquea el event loop. El
    cupo se libera en `finally`: aunque algo falle, el worker no puede
    quedar "lleno" para siempre.
    """
    job_id = solicitud.jobId

    def reportar_progreso(progreso: int, etapa: str, salidas: list[str] | None = None) -> None:
        cambios = {"progreso": progreso, "etapa": etapa}
        if salidas is not None:
            # Una versión de la canción ya está lista: va en el aviso para que
            # el usuario pueda escucharla mientras se generan las alternativas.
            cambios["outputUrls"] = salidas
        actual = trabajos[job_id].model_copy(update=cambios)
        trabajos[job_id] = actual
        # Callback de progreso (decisión 10): uno por etapa, sin reintentos.
        _notificar_callback(solicitud, actual, reintentos=0)

    try:
        proteger = None
        if config.modo_desarrollo and solicitud.operacion == "completar":
            proteger = Path(solicitud.inputUrls[0]).parent.name
        _purgar_salidas_viejas(proteger)
        resultado = ejecutar_job(solicitud, config, reportar_progreso)
        trabajos[job_id] = resultado
        _notificar_callback(solicitud, resultado, reintentos=config.callback_reintentos)
    finally:
        capacidad.liberar()


def _purgar_salidas_viejas(proteger: str | None = None) -> None:
    """Deuda técnica 4: borra carpetas de jobs viejas antes de crear una nueva."""
    en_proceso = {str(j) for j in trabajos.en_proceso()}
    for job_id in trabajos.en_proceso():
        actual = trabajos.get(job_id)
        origen = (actual.metadatos or {}).get("origenLocal") if actual else None
        if origen:
            en_proceso.add(origen)
    if proteger:
        en_proceso.add(proteger)
    try:
        purgar_salidas(config.directorio_salidas, config.retencion_salidas_horas, en_proceso)
    except Exception:
        logger.exception("Falló la limpieza de salidas viejas (el job sigue igual)")


def _notificar_callback(solicitud: SolicitudProcesar, resultado: ResultadoJob, reintentos: int) -> None:
    """
    El callback es una notificación, no una dependencia: si falla después de
    los reintentos, se registra en el log y el resultado queda disponible en
    GET /jobs/{id}. Lleva el token compartido en X-Worker-Token para que
    Django pueda rechazar callbacks falsos (decisión 14).
    """
    url = solicitud.callbackUrl or config.callback_url_default
    if not url:
        if resultado.estado != EstadoJob.PROCESANDO:
            logger.info("Job %s sin callbackUrl, no se notifica (resultado en /jobs/%s)", resultado.jobId, resultado.jobId)
        return

    encabezados = {}
    token = config.callback_token.get_secret_value() if config.callback_token else ""
    if token:  # vacío (p. ej. variable sin definir en docker-compose) = sin token
        encabezados[ENCABEZADO_TOKEN] = token

    def enviar() -> None:
        respuesta = httpx.post(url, json=resultado.model_dump(mode="json"), headers=encabezados,
                               timeout=config.callback_timeout_segundos)
        respuesta.raise_for_status()

    try:
        con_reintentos(enviar, reintentos, f"El callback del job {resultado.jobId}")
        if resultado.estado != EstadoJob.PROCESANDO:
            logger.info("Callback enviado a %s para el job %s (%s)", url, resultado.jobId, resultado.estado.value)
    except httpx.HTTPError as exc:
        logger.warning(
            "No se pudo notificar el callback a %s para el job %s (%s, %s). "
            "El job queda %s de todas formas.",
            url, resultado.jobId, type(exc).__name__, resultado.etapa, resultado.estado.value,
        )


# Demo en vivo (grabar en el navegador y escuchar la canción): SOLO en modo
# desarrollo. En producción estas rutas no existen (ver app/demo.py).
if config.modo_desarrollo:
    from app.demo import crear_router

    app.include_router(crear_router(procesar, config, trabajos.get, capacidad))
