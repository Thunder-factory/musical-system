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

    updates = {
        'status': 'failed',
        'error_message': message,
        'completed_at': timezone.now(),
    }
    if progress is not None:
        updates['progress_pct'] = max(0, min(100, progress))
    StemJob.objects.filter(id=job_id, status__in=['queued', 'processing']).update(**updates)


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
        job.error_message = None
        job.save(update_fields=['remote_job_id', 'status', 'progress_pct', 'error_message'])
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
    from apps.credits.services.credit_service import InsufficientCreditsError, deduct_credits
    from django.conf import settings
    from ml.modal_client import get_stem_job_status

    try:
        job = StemJob.objects.select_related('user').get(id=job_id)
        if job.status in FINAL_STEM_STATES:
            return
        if not job.remote_job_id:
            _mark_stem_failed(job_id, 'El job no tiene identificador remoto.')
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
        if not stems:
            _mark_stem_failed(job_id, 'Modal completó el job sin devolver stems.')
            return

        with transaction.atomic():
            locked_job = StemJob.objects.select_for_update().select_related('user').get(id=job_id)
            if locked_job.status in FINAL_STEM_STATES:
                return

            try:
                if locked_job.credits_used == 0:
                    deduct_credits(
                        locked_job.user,
                        amount=2,
                        reference_id=str(locked_job.id),
                        reference_type='stem_job',
                    )
            except InsufficientCreditsError as exc:
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
