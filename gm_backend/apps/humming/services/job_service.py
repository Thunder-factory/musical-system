"""Creación, despacho y ciclo de vida de estados de HummingJob."""

from __future__ import annotations

import os

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.humming.models import HummingJob
from apps.humming.services.constants import (
    ALLOWED_INPUT_EXTENSIONS,
    HummingValidationError,
    RESERVATION_TYPE,
    _job_prefix,
)


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

    Lanza HummingValidationError o InsufficientCreditsError sin dejar nada creado.
    """
    from apps.humming import services as pkg

    extension = _validate_upload(audio_file)
    clean_title = (title or '').strip()[:200]

    job = HummingJob.objects.create(user=user, title=clean_title, input_s3_key='')
    reservation = None
    try:
        reservation = pkg.reserve_credits(
            user,
            amount=settings.HUMMING_CREDIT_COST,
            reference_id=str(job.id),
            reference_type=RESERVATION_TYPE,
            expires_in_seconds=settings.HUMMING_QUEUE_STALE_SECONDS
            + settings.HUMMING_PROCESSING_STALE_SECONDS,
        )
        key = f'{_job_prefix(job)}/entrada{extension}'
        audio_file.seek(0)
        pkg.get_storage_client().upload_fileobj(audio_file, pkg.get_storage_bucket(), key)
    except Exception:
        if reservation is not None:
            from apps.credits.services.credit_service import release_reservation

            release_reservation(str(reservation.id))
        job.delete()
        raise

    job.input_s3_key = key
    job.save(update_fields=['input_s3_key', 'updated_at'])

    from apps.humming.tasks import dispatch_humming_job, warm_ai_gpu

    transaction.on_commit(lambda: dispatch_humming_job.delay(str(job.id)))
    transaction.on_commit(lambda: warm_ai_gpu.delay())
    return job


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

    failed_job = None
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
        failed_job = job

    if failed_job:
        try:
            from apps.notifications.services import notify_user

            title = failed_job.title or 'tu tarareo'
            notify_user(
                failed_job.user,
                type='humming_failed',
                reference_id=str(failed_job.id),
                title='No se pudo procesar el tarareo',
                message=f'Falló el procesamiento de "{title}": {message[:900]}',
                push_message='El procesamiento de tu tarareo no pudo completarse.',
            )
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                'No se pudo notificar el tarareo fallido %s', job_id,
            )
