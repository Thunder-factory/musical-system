"""
Integración con el worker de tarareo (gm_tarareo).

Contrato v1 del worker (gm_tarareo/contratos/v1, gm_tarareo/docs/INTEGRACION-DJANGO.md):

- POST {TARAREO_URL}/procesar → 202 aceptado | 503 lleno (+Retry-After) | 422 solicitud inválida
- GET  {TARAREO_URL}/jobs/{id} → mismo cuerpo que el callback (ResultadoJob)
- Callback POST a TARAREO_CALLBACK_URL con el header X-Worker-Token

Django firma las URLs de R2 en el momento de despachar (no al crear el job),
así no vencen mientras el job espera. El worker no tiene credenciales de R2.
"""

from __future__ import annotations

import logging
import os
import posixpath
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.credits.services.credit_service import (
    InsufficientCreditsError,
    confirm_reservation,
    reserve_credits,
)
from apps.humming.models import HummingJob
from ml.storage_client import (
    generate_presigned_url,
    get_storage_bucket,
    get_storage_client,
)

logger = logging.getLogger(__name__)

RESERVATION_TYPE = 'humming_job'
CONTRACT_VERSION = 1

# Salidas que pedimos para la operación "generar" y su Content-Type. Tienen que
# coincidir con TIPOS_SALIDA del worker: el PUT prefirmado incluye el
# Content-Type y, si no coincide, R2 responde 403.
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


# ── Claves de R2 ──────────────────────────────────────────────────────────────

def _job_prefix(job: HummingJob) -> str:
    return f'humming/{job.user_id}/{job.id}'


def output_key(job: HummingJob, name: str) -> str:
    return f'{_job_prefix(job)}/salidas/{name}'


def _presigned_put(key: str, content_type: str, expires: int) -> str:
    return get_storage_client().generate_presigned_url(
        'put_object',
        Params={'Bucket': get_storage_bucket(), 'Key': key, 'ContentType': content_type},
        ExpiresIn=expires,
    )


# ── Crear el job ──────────────────────────────────────────────────────────────

def _validate_upload(audio_file) -> str:
    filename = getattr(audio_file, 'name', '') or ''
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_INPUT_EXTENSIONS:
        raise HummingValidationError(
            'Formato no soportado. Usá webm, ogg, m4a, mp4, mp3, wav, aac o flac.'
        )
    max_bytes = settings.HUMMING_MAX_UPLOAD_MB * 1024 * 1024
    if not audio_file.size:
        raise HummingValidationError('El archivo está vacío.')
    if audio_file.size > max_bytes:
        raise HummingValidationError(
            f'El archivo excede el límite de {settings.HUMMING_MAX_UPLOAD_MB} MB.'
        )
    return extension


def create_humming_job(user, audio_file, *, title: str | None = None) -> HummingJob:
    """
    Valida el tarareo, reserva créditos, lo sube a R2 y encola el despacho.

    Lanza HummingValidationError o InsufficientCreditsError sin dejar nada
    creado. La duración útil (8-30 s) la valida el worker, que devuelve un
    mensaje pensado para el usuario.
    """
    extension = _validate_upload(audio_file)
    clean_title = (title or '').strip()[:200]

    job = HummingJob.objects.create(user=user, title=clean_title, input_s3_key='')
    reservation = None
    try:
        reservation = reserve_credits(
            user,
            amount=settings.HUMMING_CREDIT_COST,
            reference_id=str(job.id),
            reference_type=RESERVATION_TYPE,
            expires_in_seconds=settings.HUMMING_QUEUE_STALE_SECONDS
            + settings.HUMMING_PROCESSING_STALE_SECONDS,
        )
        key = f'{_job_prefix(job)}/entrada{extension}'
        audio_file.seek(0)
        get_storage_client().upload_fileobj(audio_file, get_storage_bucket(), key)
    except Exception:
        if reservation is not None:
            from apps.credits.services.credit_service import release_reservation

            release_reservation(str(reservation.id))
        job.delete()
        raise

    job.input_s3_key = key
    job.save(update_fields=['input_s3_key', 'updated_at'])

    from apps.humming.tasks import dispatch_humming_job

    transaction.on_commit(lambda: dispatch_humming_job.delay(str(job.id)))
    return job


# ── Despachar al worker ───────────────────────────────────────────────────────

def build_dispatch_payload(job: HummingJob) -> tuple[dict, dict[str, str]]:
    """Firma las URLs de R2 y arma el cuerpo de POST /procesar."""
    expires = settings.HUMMING_PRESIGNED_URL_SECONDS
    keys = {name: output_key(job, name) for name in OUTPUT_CONTENT_TYPES}
    payload = {
        'jobId': str(job.id),
        'version': CONTRACT_VERSION,
        'operacion': 'generar',
        'parametros': {},
        'inputUrls': [generate_presigned_url(job.input_s3_key, expires)],
        'outputUploadUrls': {
            name: _presigned_put(keys[name], content_type, expires)
            for name, content_type in OUTPUT_CONTENT_TYPES.items()
        },
        'callbackUrl': settings.TARAREO_CALLBACK_URL,
    }
    return payload, keys


def send_to_worker(payload: dict) -> DispatchOutcome:
    url = f"{settings.TARAREO_URL.rstrip('/')}/procesar"
    try:
        response = requests.post(url, json=payload, timeout=settings.TARAREO_HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise WorkerUnavailableError(f'No se pudo conectar con el worker de tarareo: {exc}') from exc

    if response.status_code == 202:
        return DispatchOutcome(accepted=True)
    if response.status_code == 503:
        try:
            retry_after = int(response.headers.get('Retry-After', '30'))
        except ValueError:
            retry_after = 30
        return DispatchOutcome(accepted=False, retry_after=max(5, min(retry_after, 300)))
    if response.status_code == 422:
        raise WorkerRejectedError(f'El worker rechazó la solicitud: {response.text[:500]}')
    raise WorkerUnavailableError(
        f'Respuesta inesperada del worker ({response.status_code}): {response.text[:200]}'
    )


def fetch_worker_status(job_id: str) -> dict | None:
    """GET /jobs/{id}. None si el worker no conoce el job (p. ej. se reinició)."""
    url = f"{settings.TARAREO_URL.rstrip('/')}/jobs/{job_id}"
    try:
        response = requests.get(url, timeout=settings.TARAREO_HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise WorkerUnavailableError(f'No se pudo consultar el worker de tarareo: {exc}') from exc
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise WorkerUnavailableError(
            f'Respuesta inesperada del worker ({response.status_code}) al consultar el job.'
        )
    return response.json()


def mark_dispatched(job_id: str, keys: dict[str, str]) -> int:
    """Marca el job como en proceso y devuelve el número de despacho (0 si ya terminó)."""
    now = timezone.now()
    with transaction.atomic():
        job = HummingJob.objects.select_for_update().get(id=job_id)
        if job.is_terminal:
            return 0
        job.status = 'processing'
        job.output_keys = keys
        job.dispatch_attempts += 1
        job.started_at = job.started_at or now
        job.last_heartbeat_at = now
        job.save(update_fields=[
            'status', 'output_keys', 'dispatch_attempts', 'started_at',
            'last_heartbeat_at', 'updated_at',
        ])
        return job.dispatch_attempts


def requeue_for_retry(job_id: str) -> bool:
    """Vuelve a encolar un job si le quedan intentos. False si ya no quedan."""
    with transaction.atomic():
        job = HummingJob.objects.select_for_update().get(id=job_id)
        if job.is_terminal:
            return False
        if job.dispatch_attempts >= settings.HUMMING_MAX_DISPATCH_ATTEMPTS:
            return False
        job.status = 'queued'
        job.available_outputs = []
        job.save(update_fields=['status', 'available_outputs', 'updated_at'])
    return True


def mark_failed(job_id: str, message: str, code: str = '') -> None:
    """Marca el job como fallido y libera la reserva de créditos."""
    from apps.credits.models import CreditReservation

    with transaction.atomic():
        job = HummingJob.objects.select_for_update().get(id=job_id)
        if job.is_terminal:
            return
        reservation = CreditReservation.objects.select_for_update().filter(
            reference_id=str(job.id),
            reference_type=RESERVATION_TYPE,
            status='reserved',
        ).first()
        if reservation:
            reservation.status = 'released'
            reservation.save(update_fields=['status', 'updated_at'])
        job.status = 'failed'
        job.error_message = message
        job.error_code = code
        job.completed_at = timezone.now()
        job.save(update_fields=[
            'status', 'error_message', 'error_code', 'completed_at', 'updated_at',
        ])


# ── Aplicar el resultado del worker (callback o polling) ──────────────────────

def _output_name(url: str) -> str:
    return posixpath.basename(unquote(urlparse(url).path))


def apply_worker_result(job_id: str, data: dict) -> str:
    """
    Aplica un ResultadoJob del worker. Idempotente: un job terminado no cambia.

    Devuelve la acción que el llamador tiene que programar después del commit:
    'none' | 'poll' (sigue procesando) | 'retry' (reintentar el despacho).
    """
    worker_status = data.get('estado')
    with transaction.atomic():
        job = HummingJob.objects.select_for_update().get(id=job_id)
        if job.is_terminal:
            return 'none'

        now = timezone.now()
        job.progress = max(0, min(100, int(data.get('progreso') or 0)))
        job.stage = (data.get('etapa') or '')[:60]
        job.last_heartbeat_at = now

        available = set(job.available_outputs or [])
        for url in data.get('outputUrls') or []:
            name = _output_name(url)
            if name in (job.output_keys or {}):
                available.add(name)
        job.available_outputs = sorted(available)

        if worker_status == WORKER_STATUS_COMPLETED:
            job.status = 'completed'
            job.progress = 100
            job.metadata = data.get('metadatos') or {}
            job.completed_at = now
            job.credits_used = _confirm_credits(job)
            job.save()
            return 'none'

        if worker_status == WORKER_STATUS_FAILED:
            code = data.get('codigoError') or ''
            message = data.get('error') or 'El worker no pudo procesar el tarareo.'
            if code == ERROR_INVALID_INPUT:
                # Definitivo (silencio, ruido, muy corto): no se reintenta y el
                # mensaje del worker ya está escrito para el usuario.
                job.metadata = data.get('metadatos') or job.metadata
                job.save()
                mark_failed(job_id, message, code)
                return 'none'
            job.error_message = message
            job.error_code = code
            job.save()
            return 'retry'

        if worker_status == WORKER_STATUS_PROCESSING:
            job.status = 'processing'
            job.save()
            return 'poll'

        logger.warning('Estado desconocido del worker para %s: %r', job_id, worker_status)
        job.save()
        return 'poll'


def _confirm_credits(job: HummingJob) -> int:
    from apps.credits.models import CreditReservation

    reservation = CreditReservation.objects.filter(
        reference_id=str(job.id),
        reference_type=RESERVATION_TYPE,
    ).first()
    if not reservation:
        return 0
    try:
        confirm_reservation(str(reservation.id))
    except (ValueError, InsufficientCreditsError) as exc:
        # El tarareo ya está procesado: no se le quita al usuario por un
        # problema de cobro. Queda registrado para revisarlo.
        logger.warning('No se pudo confirmar el cobro del tarareo %s: %s', job.id, exc)
        return 0
    return reservation.amount


# ── Elegir una versión → Song ─────────────────────────────────────────────────

def _find_version(job: HummingJob, number: int) -> dict | None:
    for version in job.versions:
        if int(version.get('numero', 0)) == number:
            return version
    return None


def choose_version(job: HummingJob, number: int, *, title: str | None = None):
    """Crea la Song de la versión elegida. Idempotente para la misma versión."""
    from apps.songs.models import Song, SongTag, Tag

    with transaction.atomic():
        job = HummingJob.objects.select_for_update().get(id=job.id)
        if job.status != 'completed':
            raise ValueError('El tarareo todavía no terminó de procesarse.')
        if job.song_id:
            if job.chosen_version == number:
                return job.song
            raise ValueError('Ya elegiste otra versión de este tarareo.')

        version = _find_version(job, number)
        if not version:
            raise ValueError('Esa versión no existe para este tarareo.')
        song_file = version.get('cancion') or ''
        if song_file not in (job.available_outputs or []):
            raise ValueError('El audio de esa versión no está disponible.')

        metadata = job.metadata or {}
        style = (version.get('estilo') or metadata.get('estilo') or '').strip()
        clean_title = (title or job.title or '').strip()[:200]
        if not clean_title:
            clean_title = f'Mi tarareo ({style})' if style else 'Mi tarareo'

        song = Song.objects.create(
            user=job.user,
            title=clean_title,
            source_type='hummed',
            description=metadata.get('estiloMensaje') or None,
            prompt=style or None,
            instrumental=True,
            lyrics_source='user',
            audio_duration=float(metadata.get('duracionCancionSegundos') or 0),
            audio_s3_key=job.output_keys[song_file],
            status='ready',
            is_public=False,
        )
        if style:
            tag, _ = Tag.objects.get_or_create(name=style.lower(), defaults={'category': 'genre'})
            SongTag.objects.get_or_create(song=song, tag=tag)

        job.song = song
        job.chosen_version = number
        job.save(update_fields=['song', 'chosen_version', 'updated_at'])
        return song

