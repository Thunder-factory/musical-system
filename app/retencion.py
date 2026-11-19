"""
Límites de lo que el worker guarda (deuda técnica 4).

Antes, el dict de jobs en memoria y la carpeta salidas/ crecían sin límite:
un worker que corre semanas terminaba sin RAM o sin disco.

- `RegistroJobs`: los jobs para GET /jobs/{id}. Los terminados se olvidan
  después de `retencion_jobs_minutos` (Django ya recibió el callback; esto
  es solo el respaldo de polling) y nunca hay más de `maximo_jobs_en_memoria`.
  Los que están en proceso no se olvidan nunca.
- `purgar_salidas`: borra carpetas de jobs más viejas que
  `retencion_salidas_horas`. En producción casi no hay nada que borrar (con
  outputUploadUrls la carpeta se borra al subir); en desarrollo evita que
  salidas/ crezca para siempre.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from app.modelos import EstadoJob, ResultadoJob

logger = logging.getLogger(__name__)


class RegistroJobs:
    def __init__(self, retencion_segundos: float, maximo: int, reloj: Callable[[], float] = time.monotonic) -> None:
        self._jobs: dict[UUID, ResultadoJob] = {}
        self._terminado_en: dict[UUID, float] = {}
        self._candado = threading.Lock()
        self._retencion = retencion_segundos
        self._maximo = maximo
        self._reloj = reloj

    def __len__(self) -> int:
        return len(self._jobs)

    def get(self, job_id: UUID) -> ResultadoJob | None:
        return self._jobs.get(job_id)

    def __getitem__(self, job_id: UUID) -> ResultadoJob:
        return self._jobs[job_id]

    def __setitem__(self, job_id: UUID, resultado: ResultadoJob) -> None:
        with self._candado:
            self._jobs[job_id] = resultado
            if resultado.estado in (EstadoJob.COMPLETADO, EstadoJob.FALLIDO):
                self._terminado_en[job_id] = self._reloj()
            else:
                self._terminado_en.pop(job_id, None)
            self._purgar()

    def en_proceso(self) -> set[UUID]:
        with self._candado:
            return {j for j, r in self._jobs.items() if r.estado == EstadoJob.PROCESANDO}

    def clear(self) -> None:
        with self._candado:
            self._jobs.clear()
            self._terminado_en.clear()

    def _purgar(self) -> None:
        """Se llama con el candado tomado. Solo olvida jobs terminados."""
        ahora = self._reloj()
        vencidos = [j for j, t in self._terminado_en.items() if ahora - t > self._retencion]
        sobrantes = len(self._jobs) - len(vencidos) - self._maximo
        if sobrantes > 0:  # además, los terminados más viejos hasta volver al máximo
            restantes = sorted((t, j) for j, t in self._terminado_en.items() if j not in set(vencidos))
            vencidos += [j for _, j in restantes[:sobrantes]]
        for job_id in vencidos:
            self._jobs.pop(job_id, None)
            self._terminado_en.pop(job_id, None)


def purgar_salidas(directorio: Path, retencion_horas: float, en_proceso: set[str] | None = None,
                   ahora: float | None = None) -> int:
    """
    Borra las carpetas de jobs (dentro de `directorio`) sin cambios hace más de
    `retencion_horas`. Nunca toca las de jobs en proceso. Devuelve cuántas borró.
    """
    if not directorio.is_dir():
        return 0
    ahora = ahora if ahora is not None else time.time()
    limite = ahora - retencion_horas * 3600
    en_proceso = en_proceso or set()
    borradas = 0
    for carpeta in directorio.iterdir():
        if not carpeta.is_dir() or carpeta.name in en_proceso:
            continue
        try:
            if carpeta.stat().st_mtime < limite:
                shutil.rmtree(carpeta)
                borradas += 1
        except OSError:
            logger.warning("No se pudo borrar la carpeta vieja %s", carpeta, exc_info=True)
    if borradas:
        logger.info("Se borraron %d carpeta(s) de jobs de más de %.0f h en %s", borradas, retencion_horas, directorio)
    return borradas
