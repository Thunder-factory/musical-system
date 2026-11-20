"""Constantes, excepciones y utilidades base del dominio de tarareo."""

from __future__ import annotations

from dataclasses import dataclass

from apps.humming.models import HummingJob

RESERVATION_TYPE = 'humming_job'
CONTRACT_VERSION = 1

# Salidas pedidas para la operación "generar" y su Content-Type (coinciden con TIPOS_SALIDA).
OUTPUT_CONTENT_TYPES: dict[str, str] = {
    'cancion.mp3': 'audio/mpeg',
    'cancion-2.mp3': 'audio/mpeg',
    'cancion-3.mp3': 'audio/mpeg',
    'arreglo.mid': 'audio/midi',
    'arreglo-2.mid': 'audio/midi',
    'arreglo-3.mid': 'audio/midi',
    'melodia.mid': 'audio/midi',
    'analisis.json': 'application/json',
    'partitura.musicxml': 'application/vnd.recordare.musicxml+xml',
}

ALLOWED_INPUT_EXTENSIONS = frozenset(
    {'.webm', '.ogg', '.oga', '.m4a', '.mp4', '.mp3', '.wav', '.aac', '.flac'}
)

WORKER_STATUS_PROCESSING = 'PROCESANDO'
WORKER_STATUS_COMPLETED = 'COMPLETADO'
WORKER_STATUS_FAILED = 'FALLIDO'
ERROR_INVALID_INPUT = 'ENTRADA_INVALIDA'
ERROR_INTERNAL = 'ERROR_INTERNO'


class HummingValidationError(ValueError):
    """El archivo subido no se puede enviar al worker."""


class WorkerRejectedError(Exception):
    """El worker rechazó la solicitud (422): es un bug de Django, no se reintenta."""


class WorkerUnavailableError(Exception):
    """No se pudo hablar con el worker (red, 5xx distinto de 503): reintentable."""


@dataclass(frozen=True)
class DispatchOutcome:
    accepted: bool
    retry_after: int = 0


def _job_prefix(job: HummingJob) -> str:
    return f'humming/{job.user_id}/{job.id}'


def output_key(job: HummingJob, name: str) -> str:
    return f'{_job_prefix(job)}/salidas/{name}'
