"""
Subida de las salidas a Cloudflare R2 con URLs prefirmadas (bloque 2).

El worker NO tiene credenciales de R2: Django firma una URL PUT por archivo
al despachar el job y el worker solo hace PUT a cada una (decisión 9 de
docs/ARQUITECTURA.md). Funciona igual con cualquier almacenamiento compatible
con S3 (MinIO en desarrollo).

Detalles de R2:
- El PUT tiene que mandar el MISMO Content-Type con que se firmó la URL; si
  no, R2 rechaza la subida (403). Por eso los tipos están fijos en el
  contrato (`TIPOS_SALIDA` en modelos.py).
- La URL lleva la firma en la query: nunca se loguea entera. A Django se le
  devuelve la URL SIN la firma (sirve para identificar el objeto, no para
  leerlo).
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.modelos import TIPOS_SALIDA
from app.pipeline.excepciones import ErrorAlmacenamiento
from app.pipeline.ingesta import describir_url
from app.reintentos import con_reintentos

logger = logging.getLogger(__name__)


def subir_archivo(ruta: Path, url: str, tipo: str, config) -> None:
    def put() -> None:
        with open(ruta, "rb") as archivo:
            respuesta = httpx.put(
                url, content=archivo.read(), headers={"Content-Type": tipo},
                timeout=config.subida_timeout_segundos,
            )
        respuesta.raise_for_status()

    con_reintentos(put, config.subida_reintentos, f"La subida de {ruta.name}")


def subir_salidas(archivos: dict[str, Path], urls: dict[str, str], config) -> list[str]:
    """
    Sube cada archivo pedido en `urls` (nombre → URL PUT). Devuelve las URLs
    sin firma, en el orden de `urls`. Lanza ErrorAlmacenamiento si alguna
    falla después de los reintentos.
    """
    subidas = []
    for nombre, url in urls.items():
        ruta = archivos.get(nombre)
        if ruta is None or not ruta.is_file():
            raise ErrorAlmacenamiento(f"El worker no generó '{nombre}', que se pidió en outputUploadUrls.")
        try:
            subir_archivo(ruta, url, TIPOS_SALIDA[nombre], config)
        except httpx.HTTPStatusError as exc:
            codigo = exc.response.status_code
            pista = " (¿URL vencida o firmada con otro Content-Type?)" if codigo in (400, 403) else ""
            raise ErrorAlmacenamiento(
                f"No se pudo subir {nombre} a {describir_url(url)}: el almacenamiento respondió {codigo}{pista}."
            ) from exc
        except httpx.HTTPError as exc:
            raise ErrorAlmacenamiento(
                f"No se pudo subir {nombre} a {describir_url(url)}: {type(exc).__name__}."
            ) from exc
        logger.info("Subido %s (%d bytes) a %s", nombre, ruta.stat().st_size, describir_url(url))
        subidas.append(describir_url(url))
    return subidas
