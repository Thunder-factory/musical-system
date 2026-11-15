import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 3
FINAL_STEM_STATES = {'completed', 'failed'}


def _schedule_stem_poll(job_id: str, countdown: int = POLL_INTERVAL_SECONDS):
    poll_stem_job.apply_async(args=[job_id], countdown=countdown)


def _mark_stem_failed(job_id: str, message: str, progress: int | None = None):
    from apps.stems.models import StemJob
    from apps.credits.services.credit_service import release_reservation
    from apps.credits.models import CreditReservation

    updates = {
        'status': 'failed',
        'error_message': message,
        'completed_at': timezone.now(),
    }
    if progress is not None:
        updates['progress_pct'] = max(0, min(100, progress))
    StemJob.objects.filter(id=job_id, status__in=['queued', 'processing']).update(**updates)
    reservation = CreditReservation.objects.filter(
        reference_id=job_id,
        reference_type='stem_job',
        status='reserved',
    ).first()
    if reservation:
        release_reservation(str(reservation.id))


def _validate_stem_objects(stems: dict):
    from ml.storage_client import get_storage_bucket, get_storage_client

    required = {'vocals', 'no_vocals'}
    if not required.issubset(stems):
        raise ValueError('Modal no devolvió vocals y no_vocals.')
    client = get_storage_client()
    bucket = get_storage_bucket()
    for stem_type in required:
        key = stems[stem_type]
        if not isinstance(key, str) or not key:
            raise ValueError(f'Clave inválida para {stem_type}.')
        metadata = client.head_object(Bucket=bucket, Key=key)
        if int(metadata.get('ContentLength', 0)) <= 0:
            raise ValueError(f'El objeto R2 {stem_type} está vacío.')


def _settle_stem_credits(job):
    """Confirm a stem reservation exactly once, including legacy jobs."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import (
        confirm_reservation,
        deduct_credits,
    )

    reservation = CreditReservation.objects.filter(
        user=job.user,
        reference_id=job.id,
        reference_type='stem_job',
    ).first()
    if reservation and reservation.status == 'reserved':
        confirm_reservation(str(reservation.id))
    elif reservation and reservation.status == 'confirmed':
        return
    elif reservation and reservation.status == 'released':
        raise ValueError('La reserva de créditos fue liberada.')
    elif job.credits_used == 0:
        deduct_credits(
            job.user,
            amount=2,
            reference_id=str(job.id),
            reference_type='stem_job',
        )


@shared_task(bind=True, max_retries=3)
def process_stem_job(self, job_id: str):
    """Envía el job a Modal y delega su seguimiento a una tarea separada."""
    from apps.stems.models import StemJob
    from django.conf import settings
    from ml.modal_client import submit_stem_job

    try:
        job = StemJob.objects.get(id=job_id)
        if job.status in FINAL_STEM_STATES:
            return

        if job.remote_job_id:
            _schedule_stem_poll(job_id, countdown=0)
            return

        response = submit_stem_job(
            settings.MODAL_ENDPOINT_SEPARATE_STEMS,
            {'s3_key': job.source_audio_url, 'client_job_id': str(job.id)},
        )
        job.remote_job_id = response['remote_job_id']
        job.status = 'queued'
        job.progress_pct = 0
        job.started_at = timezone.now()
        job.error_message = None
        job.save(update_fields=['remote_job_id', 'status', 'progress_pct', 'started_at', 'error_message'])
        _schedule_stem_poll(job_id, countdown=0)
    except Exception as exc:
        logger.exception('No se pudo iniciar la separación de stems %s', job_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        _mark_stem_failed(job_id, str(exc))


@shared_task(bind=True, max_retries=5)
def poll_stem_job(self, job_id: str):
    """Sincroniza el estado remoto de Modal con el StemJob local."""
    from apps.stems.models import StemJob, StemFile
    from apps.credits.services.credit_service import (
        InsufficientCreditsError,
    )
    from django.conf import settings
    from ml.modal_client import get_stem_job_status

    try:
        job = StemJob.objects.select_related('user').get(id=job_id)
        if job.status in FINAL_STEM_STATES:
            return
        if not job.remote_job_id:
            _mark_stem_failed(job_id, 'El job no tiene identificador remoto.')
            return
        if job.started_at and (
            timezone.now() - job.started_at
        ).total_seconds() > settings.STEM_REMOTE_TIMEOUT_SECONDS:
            _mark_stem_failed(
                job_id,
                'La separación excedió el tiempo máximo permitido.',
                job.progress_pct,
            )
            return

        remote = get_stem_job_status(
            settings.MODAL_ENDPOINT_SEPARATE_STEMS,
            job.remote_job_id,
        )
        remote_status = remote.get('status')
        progress = max(0, min(100, int(remote.get('progress_pct', job.progress_pct))))

        if remote_status in {'queued', 'processing'}:
            update_fields = ['status', 'progress_pct']
            job.status = remote_status
            job.progress_pct = progress
            if remote_status == 'processing' and job.started_at is None:
                job.started_at = timezone.now()
                update_fields.append('started_at')
            job.save(update_fields=update_fields)
            _schedule_stem_poll(job_id)
            return

        if remote_status == 'failed':
            _mark_stem_failed(
                job_id,
                remote.get('error_message') or 'Modal no pudo separar las pistas.',
                progress,
            )
            return

        if remote_status != 'completed':
            _mark_stem_failed(job_id, f'Estado remoto desconocido: {remote_status}')
            return

        stems = remote.get('stems') or {}
        try:
            _validate_stem_objects(stems)
        except Exception as exc:
            _mark_stem_failed(job_id, str(exc), progress)
            return

        with transaction.atomic():
            locked_job = StemJob.objects.select_for_update().select_related('user').get(id=job_id)
            if locked_job.status in FINAL_STEM_STATES:
                return

            try:
                _settle_stem_credits(locked_job)
            except (InsufficientCreditsError, ValueError) as exc:
                locked_job.status = 'failed'
                locked_job.progress_pct = progress
                locked_job.error_message = str(exc)
                locked_job.completed_at = timezone.now()
                locked_job.save(update_fields=['status', 'progress_pct', 'error_message', 'completed_at'])
                return

            for stem_type, s3_key in stems.items():
                StemFile.objects.update_or_create(
                    stem_job=locked_job,
                    stem_type=stem_type,
                    defaults={'audio_s3_key': s3_key},
                )

            locked_job.status = 'completed'
            locked_job.progress_pct = 100
            locked_job.credits_used = 2
            locked_job.completed_at = timezone.now()
            locked_job.error_message = None
            locked_job.save(
                update_fields=[
                    'status', 'progress_pct', 'credits_used', 'completed_at', 'error_message'
                ]
            )

        try:
            from apps.notifications.services import notify_user
            notify_user(job.user, type='stem_ready', reference_id=str(job.id))
        except Exception:
            logger.exception('No se pudo notificar la separación de stems %s', job.id)
    except Exception as exc:
        logger.exception('Error consultando la separación de stems %s', job_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=min(60, 10 * (self.request.retries + 1)))
        _mark_stem_failed(job_id, str(exc))
