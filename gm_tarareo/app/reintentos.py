"""
Reintentos con espera creciente para operaciones de red (subida a R2, callback).

Solo se reintenta lo que puede salir bien al segundo intento: errores de red,
timeouts y respuestas 5xx (el otro lado tuvo un problema momentáneo). Un 4xx
no se reintenta: es un error de la solicitud (URL vencida, firma inválida,
token incorrecto) y repetirla daría lo mismo.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")
ESPERA_BASE_SEGUNDOS = 1.0


def es_reintentable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


def con_reintentos(
    operacion: Callable[[], T],
    reintentos: int,
    que: str,
    dormir: Callable[[float], None] | None = None,
) -> T:
    """
    Ejecuta `operacion`; si falla con un error reintentable, espera 1 s, 2 s,
    4 s... y vuelve a intentar, hasta `reintentos` veces más. Si se agotan (o
    el error no es reintentable), relanza la última excepción.
    """
    for intento in range(reintentos + 1):
        try:
            return operacion()
        except Exception as exc:
            if intento == reintentos or not es_reintentable(exc):
                raise
            espera = ESPERA_BASE_SEGUNDOS * 2 ** intento
            logger.warning("%s falló (%s); reintento %d/%d en %.0f s",
                           que, type(exc).__name__, intento + 1, reintentos, espera)
            (dormir or time.sleep)(espera)
    raise AssertionError("inalcanzable")
