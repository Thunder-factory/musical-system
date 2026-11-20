"""Tareas Celery que envían el doblaje a Modal y sincronizan su estado."""

import json
import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

FINAL_STATES = {'completed', 'failed'}
RESERVATION_TYPE = 'translation_job'
REQUIRED_OUTPUTS = ('video', 'audio', 'lyrics')
MAX_LYRICS_BYTES = 2 * 1024 * 1024


def _notify_translation_failure(job_id: str, message: str) -> None:
    from apps.notifications.services import notify_user
    from apps.translations.models import TranslationJob

    job = TranslationJob.objects.select_related('user').filter(id=job_id).first()
    if not job:
        return
    notify_user(
        job.user,
        type='translation_failed',
        reference_id=str(job.id),
        title='No se pudo completar la traducción',
        message=f'Falló la traducción de "{job.song_title or job.source_filename}": {message[:900]}',
        push_message='La traducción de tu video no pudo completarse.',
    )


def _notify_translation_ready(job_id: str) -> None:
    from apps.notifications.services import notify_user
    from apps.translations.models import TranslationJob

    job = TranslationJob.objects.select_related('user').filter(id=job_id).first()
    if not job:
        return
    notify_user(
        job.user,
        type='translation_ready',
        reference_id=str(job.id),
        title='Traducción lista',
        message=f'La traducción de "{job.song_title or job.source_filename}" ya está disponible.',
    )


def _schedule_poll(job_id: str, countdown: int | None = None):
    if countdown is None:
        countdown = settings.TRANSLATION_POLL_INTERVAL_SECONDS
    poll_translation_job.apply_async(args=[job_id], countdown=countdown)


def _mark_failed(job_id: str, message: str, progress: int | None = None):
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import release_reservation
    from apps.translations.models import TranslationJob

    updates = {
        'status': 'failed',
        'error_message': message[:1000],
        'completed_at': timezone.now(),
        'updated_at': timezone.now(),
    }
    if progress is not None:
        updates['progress_pct'] = max(0, min(100, progress))
    updated = TranslationJob.objects.filter(
        id=job_id,
        status__in=['queued', 'processing'],
    ).update(**updates)

    reservation = CreditReservation.objects.filter(
        reference_id=job_id,
        reference_type=RESERVATION_TYPE,
        status='reserved',
    ).first()
    if reservation:
        try:
            release_reservation(str(reservation.id))
        except Exception:
            logger.exception('No se pudo liberar la reserva de traducción %s', job_id)
    if updated:
        try:
            _notify_translation_failure(job_id, message)
        except Exception:
            logger.exception('No se pudo notificar la traducción fallida %s', job_id)


def _load_outputs(outputs: dict) -> dict:
    """Comprueba que Modal subió los tres archivos y devuelve la letra ya leída."""
    from ml.storage_client import get_storage_bucket, get_storage_client

    missing = [name for name in REQUIRED_OUTPUTS if not outputs.get(name)]
    if missing:
        raise ValueError('Modal no devolvió: ' + ', '.join(missing))

    client = get_storage_client()
    bucket = get_storage_bucket()
    for name in REQUIRED_OUTPUTS:
        metadata = client.head_object(Bucket=bucket, Key=outputs[name])
        size = int(metadata.get('ContentLength', 0))
        if size <= 0:
            raise ValueError(f'El archivo de resultado "{name}" está vacío.')
        if name == 'lyrics' and size > MAX_LYRICS_BYTES:
            raise ValueError('El archivo de letra es demasiado grande.')

    body = client.get_object(Bucket=bucket, Key=outputs['lyrics'])['Body'].read()
    lyrics = json.loads(body.decode('utf-8'))
    if not isinstance(lyrics, dict) or not isinstance(lyrics.get('frases'), list):
        raise ValueError('La letra devuelta por Modal no tiene el formato esperado.')
    return lyrics


def _settle_credits(job):
    """Confirma la reserva de créditos una sola vez."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import confirm_reservation

    reservation = CreditReservation.objects.filter(
        user=job.user,
        reference_id=job.id,
        reference_type=RESERVATION_TYPE,
    ).first()
    if reservation is None:
        raise ValueError('No existe la reserva de créditos de la traducción.')
    if reservation.status == 'reserved':
        confirm_reservation(str(reservation.id))
    elif reservation.status == 'released':
        raise ValueError('La reserva de créditos fue liberada.')


@shared_task(bind=True, max_retries=3)
def process_translation_job(self, job_id: str):
    """Envía el trabajo a Modal y delega su seguimiento a poll_translation_job."""
    from apps.translations.models import TranslationJob
    from ml.modal_client import submit_translation_job

    try:
        job = TranslationJob.objects.get(id=job_id)
        if job.status in FINAL_STATES:
            return
        if job.remote_job_id:
            _schedule_poll(job_id, countdown=0)
            return
        if not settings.MODAL_ENDPOINT_TRANSLATE_VIDEO:
            _mark_failed(job_id, 'El servicio de traducción no está configurado (MODAL_ENDPOINT_TRANSLATE_VIDEO).')
            return

        response = submit_translation_job(
            settings.MODAL_ENDPOINT_TRANSLATE_VIDEO,
            {
                's3_key': job.source_video_key,
                'client_job_id': str(job.id),
                'target_language': job.target_language,
                'title': job.song_title or None,
                'artist': job.song_artist or None,
                'mode': settings.TRANSLATION_MODE,
                'sing': settings.TRANSLATION_SING,
                'debug': settings.TRANSLATION_DEBUG,
            },
        )
        job.remote_job_id = response['remote_job_id']
        job.status = 'queued'
        job.stage = response.get('stage') or 'en_cola'
        job.progress_pct = int(response.get('progress_pct') or 0)
        job.started_at = timezone.now()
        job.error_message = None
        job.save(update_fields=[
            'remote_job_id', 'status', 'stage', 'progress_pct',
            'started_at', 'error_message', 'updated_at',
        ])
        _schedule_poll(job_id, countdown=0)
    except Exception as exc:
        logger.exception('No se pudo iniciar la traducción %s', job_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        _mark_failed(job_id, str(exc))


@shared_task(bind=True, max_retries=5)
def poll_translation_job(self, job_id: str):
    """Sincroniza el estado remoto de Modal con el TranslationJob local."""
    from apps.translations.models import TranslationJob
    from ml.modal_client import get_translation_job_status

    try:
        job = TranslationJob.objects.select_related('user').get(id=job_id)
        if job.status in FINAL_STATES:
            return
        if not job.remote_job_id:
            _mark_failed(job_id, 'El trabajo no tiene identificador remoto.')
            return
        if job.started_at and (
            timezone.now() - job.started_at
        ).total_seconds() > settings.TRANSLATION_REMOTE_TIMEOUT_SECONDS:
            _mark_failed(job_id, 'La traducción excedió el tiempo máximo permitido.', job.progress_pct)
            return

        remote = get_translation_job_status(settings.MODAL_ENDPOINT_TRANSLATE_VIDEO, job.remote_job_id)
        remote_status = remote.get('status')
        progress = max(0, min(100, int(remote.get('progress_pct', job.progress_pct) or 0)))
        stage = (remote.get('stage') or job.stage or '')[:30]

        if remote_status in {'queued', 'processing'}:
            job.status = remote_status
            job.progress_pct = progress
            job.stage = stage
            if remote.get('mode'):
                job.mode = str(remote['mode'])[:20]
            job.save(update_fields=['status', 'progress_pct', 'stage', 'mode', 'updated_at'])
            _schedule_poll(job_id)
            return

        if remote_status == 'failed':
            _mark_failed(
                job_id,
                remote.get('error_message') or 'Modal no pudo traducir el video.',
                progress,
            )
            return

        if remote_status != 'completed':
            _mark_failed(job_id, f'Estado remoto desconocido: {remote_status}')
            return

        outputs = remote.get('outputs') or {}
        try:
            lyrics = _load_outputs(outputs)
        except Exception as exc:
            _mark_failed(job_id, f'Resultado inválido: {exc}', progress)
            return

        settlement_error = None
        with transaction.atomic():
            locked = TranslationJob.objects.select_for_update().select_related('user').get(id=job_id)
            if locked.status in FINAL_STATES:
                return
            try:
                _settle_credits(locked)
            except Exception as exc:
                locked.status = 'failed'
                locked.error_message = str(exc)
                locked.completed_at = timezone.now()
                locked.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
                settlement_error = str(exc)

            if settlement_error is None:
                locked.status = 'completed'
                locked.stage = 'completado'
                locked.progress_pct = 100
                locked.mode = str(remote.get('mode') or locked.mode)[:20]
                locked.result_video_key = outputs['video']
                locked.result_audio_key = outputs['audio']
                locked.result_lyrics_key = outputs['lyrics']
                locked.lyrics = lyrics
                locked.details = remote.get('details') or {}
                locked.credits_used = settings.TRANSLATION_CREDIT_COST
                locked.completed_at = timezone.now()
                locked.error_message = None
                locked.save()
                validacion = locked.details.get('validacion') if isinstance(locked.details, dict) else None
                if validacion and not validacion.get('completo', True):
                    logger.warning(
                        'Traducción %s incompleta: %s s sin voz traducida, %d caídas de volumen, %d versos largos',
                        job_id, validacion.get('segundos_sin_voz'), len(validacion.get('caidas_de_volumen') or []),
                        len(validacion.get('versos_largos') or []))

        if settlement_error is not None:
            try:
                _notify_translation_failure(job_id, settlement_error)
            except Exception:
                logger.exception('No se pudo notificar la traducción fallida %s', job_id)
            return

        try:
            _notify_translation_ready(job_id)
        except Exception:
            logger.exception('No se pudo notificar la traducción lista %s', job_id)
    except Exception as exc:
        logger.exception('Error consultando la traducción %s', job_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=min(60, 10 * (self.request.retries + 1)))
        _mark_failed(job_id, str(exc))
