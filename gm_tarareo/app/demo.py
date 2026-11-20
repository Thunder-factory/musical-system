"""
Demo en vivo: grabar un tarareo en el navegador y escuchar la canción.

SOLO existe con TARAREO_MODO_DESARROLLO=true (main.py no registra estas rutas
en producción). En producción el audio llega por URL de R2 y lo despacha
Django; acá el navegador sube la grabación directo al worker, que la guarda en
disco y crea un job local por el mismo camino que POST /procesar (capacidad,
progreso, núcleo). Así la demo prueba exactamente el pipeline real.

    GET  /demo                          la página (app/demo.html)
    POST /demo/tarareo                  cuerpo = el audio grabado → 202 {jobId}
    GET  /demo/archivo/{jobId}/{nombre} una salida del job (cancion.mp3, ...)
    POST /demo/eleccion/{jobId}         {"version": n}: qué versión le gustó más

El navegador permite usar el micrófono en http://localhost (contexto seguro).
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.modelos import TIPOS_SALIDA, RespuestaProcesar, SolicitudProcesar
from app.versiones import analisis_guardado, completa_guardada, identificador_version

logger = logging.getLogger(__name__)

PAGINA = Path(__file__).with_name("demo.html")
CARPETA_ENTRADAS = "demo-entradas"
# Lo que graba MediaRecorder según el navegador → extensión (ffmpeg detecta el
# formato real por el contenido; la extensión es solo informativa).
EXTENSIONES = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/mpeg": ".mp3",
               "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/x-m4a": ".m4a"}

ARCHIVO_ELECCIONES = "elecciones.csv"
COLUMNAS_ELECCIONES = ("fecha", "jobId", "preset", "sugerido", "version",
                       "bpm", "modo", "densidad", "articulacion", "rango", "saltos", "repeticion")

class Eleccion(BaseModel):
    version: int = Field(ge=1, le=3)


class PedidoCompleta(Eleccion):
    anticipar: bool = False


Procesar = Callable[[SolicitudProcesar, BackgroundTasks], Awaitable[RespuestaProcesar]]


def crear_router(procesar: Procesar, config, consultar=lambda _id: None, capacidad=None) -> APIRouter:
    router = APIRouter(prefix="/demo", include_in_schema=False)

    @router.get("", response_class=HTMLResponse)
    async def pagina() -> str:
        return PAGINA.read_text(encoding="utf-8")

    @router.post("/tarareo", status_code=202, response_model=RespuestaProcesar)
    async def subir_tarareo(request: Request, tareas: BackgroundTasks) -> RespuestaProcesar:
        datos = await request.body()
        if not datos:
            raise HTTPException(status_code=422, detail="No llegó audio. Grabá de nuevo.")
        if len(datos) > config.descarga_tamano_maximo_bytes:
            raise HTTPException(status_code=413, detail="La grabación es demasiado grande.")
        tipo = request.headers.get("content-type", "").split(";")[0].strip().lower()
        job_id = uuid4()
        carpeta = config.directorio_salidas / CARPETA_ENTRADAS
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / f"{job_id}{EXTENSIONES.get(tipo, '.webm')}"
        ruta.write_bytes(datos)
        logger.info("Demo: tarareo recibido (%d bytes, %s) → job %s", len(datos), tipo or "sin tipo", job_id)
        return await procesar(SolicitudProcesar(jobId=job_id, inputUrls=[str(ruta.resolve())],
                                               operacion="muestras"), tareas)

    @router.post("/completa/{origen}")
    async def completar(origen: UUID, pedido: PedidoCompleta, tareas: BackgroundTasks) -> JSONResponse:
        try:
            analisis = await run_in_threadpool(analisis_guardado, origen, config)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="No existe el tarareo o venció su tiempo de guardado.") from exc
        if pedido.version not in {v.numero for v in analisis.versiones}:
            raise HTTPException(status_code=422, detail="Esa versión no está disponible.")
        job_id = identificador_version(origen, pedido.version, config)
        if await run_in_threadpool(completa_guardada, job_id, pedido.version, config):
            return JSONResponse({"jobId": str(job_id), "estado": "COMPLETADO", "cache": True})
        actual = consultar(job_id)
        if actual is not None and actual.estado.value == "PROCESANDO":
            return JSONResponse({"jobId": str(job_id), "estado": "PROCESANDO", "cache": False}, status_code=202)
        # Como máximo un trabajo anticipado. Dejar un cupo para una elección
        # explícita y no anticipar en máquinas con capacidad de un solo job.
        if pedido.anticipar and (capacidad is None or capacidad.capacidad < 2 or capacidad.ocupados > 0):
            raise HTTPException(status_code=503, detail="La anticipación espera un cupo libre.",
                                headers={"Retry-After": "3"})
        ruta = (config.directorio_job(origen) / "analisis.json").resolve()
        respuesta = await procesar(SolicitudProcesar(
            jobId=job_id, inputUrls=[str(ruta)], operacion="completar", versionElegida=pedido.version,
        ), tareas)
        return JSONResponse({**respuesta.model_dump(mode="json"), "cache": False}, status_code=202)

    @router.get("/completas/{origen}")
    def completas(origen: UUID) -> dict:
        try:
            analisis = analisis_guardado(origen, config)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="No existe el tarareo.") from exc
        versiones = []
        for v in analisis.versiones:
            job_id = identificador_version(origen, v.numero, config)
            estado = consultar(job_id)
            terminada = completa_guardada(job_id, v.numero, config)
            versiones.append({"numero": v.numero, "jobId": str(job_id),
                              "estado": "COMPLETADO" if terminada else (estado.estado.value if estado else "PENDIENTE"),
                              "error": estado.error if estado else None,
                              "cancion": "cancion.mp3" if v.numero == 1 else f"cancion-{v.numero}.mp3"})
        return {"versiones": versiones}

    @router.get("/archivo/{job_id}/{nombre}")
    async def archivo(job_id: UUID, nombre: str) -> FileResponse:
        # `nombre` solo puede ser una de las salidas conocidas: nada de rutas arbitrarias.
        if nombre not in TIPOS_SALIDA:
            raise HTTPException(status_code=404, detail="Archivo desconocido")
        ruta = config.directorio_job(job_id) / nombre
        if not ruta.is_file():
            raise HTTPException(status_code=404, detail="Todavía no existe (¿el job terminó?)")
        return FileResponse(ruta, media_type=TIPOS_SALIDA[nombre], filename=nombre)

    @router.post("/eleccion/{job_id}", status_code=204)
    def elegir(job_id: UUID, eleccion: Eleccion) -> None:
        """
        Guarda qué versión eligió el usuario en salidas/elecciones.csv, con los
        rasgos del tarareo: el mismo formato que tests/audio/estilos_validados.csv,
        así una elección se puede sumar a la calibración de la etapa 6.5.
        """
        ruta_analisis = config.directorio_job(job_id) / "analisis.json"
        if not ruta_analisis.is_file():
            raise HTTPException(status_code=404, detail="No existe ese job")
        analisis = json.loads(ruta_analisis.read_text(encoding="utf-8"))
        versiones = {v["numero"]: v for v in analisis["versiones"]}
        version = versiones.get(eleccion.version)
        if version is None:
            raise HTTPException(status_code=422, detail="Versión inexistente")

        ruta_csv = config.directorio_salidas / ARCHIVO_ELECCIONES
        nuevo = not ruta_csv.is_file()
        rasgos = analisis["estilo"]["rasgos"]
        with open(ruta_csv, "a", newline="", encoding="utf-8") as archivo:
            escritor = csv.writer(archivo)
            if nuevo:
                escritor.writerow(COLUMNAS_ELECCIONES)
            escritor.writerow([
                datetime.now(UTC).astimezone().isoformat(timespec="seconds"), str(job_id), version["estilo"],
                analisis["estilo"]["preset"], version["numero"],
                *(rasgos[c] for c in ("bpm", "modo", "densidad", "articulacion", "rango", "saltos", "repeticion")),
            ])
        logger.info("Demo: en el job %s eligieron la versión %d (%s; el sistema sugería %s)",
                    job_id, version["numero"], version["estilo"], analisis["estilo"]["preset"])

    return router
