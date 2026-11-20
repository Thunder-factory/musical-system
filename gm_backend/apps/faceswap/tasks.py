import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

FINAL_FACESWAP_STATES = {'completed', 'failed'}
REFERENCE_TYPE = 'faceswap_job'
RESULT_PREFIX = 'faceswap/results/'


def _notify_faceswap_failure(job_id: str, message: str) -> None:
    from apps.faceswap.models import FaceSwapJob
    from apps.notifications.services import notify_user

    job = FaceSwapJob.objects.select_related('user').filter(id=job_id).first()
    if not job:
        return
    notify_user(
        job.user,
        type='faceswap_failed',
        reference_id=str(job.id),
        title='No se pudo procesar el video',
        message=f'Falló el procesamiento del video: {message[:900]}',
        push_message='El procesamiento de tu video no pudo completarse.',
    )


def _schedule_faceswap_poll(job_id: str, countdown: int | None = None):
    """Programa el siguiente sondeo del estado remoto en Modal."""
    if countdown is None:
        countdown = settings.FACESWAP_POLL_INTERVAL_SECONDS
    poll_faceswap_job.apply_async(args=[job_id], countdown=countdown)


def _cleanup_inputs(job_id: str) -> None:
    """Borra de R2 la foto y el clip propio del job (best effort, nunca lanza)."""
    try:
        from apps.faceswap.models import FaceSwapJob
        from ml.storage_client import delete_file

        job = FaceSwapJob.objects.filter(id=job_id).first()
        if not job:
            return
        keys = [job.photo_s3_key]
        updates = {'photo_s3_key': None}
        # Nunca se borra el video de una plantilla: lo comparten todos los jobs.
        if job.source_type == 'upload':
            keys.append(job.source_video_s3_key)
            updates['source_video_s3_key'] = None
        for key in [key for key in keys if key]:
            try:
                delete_file(key)
            except Exception:
                logger.exception('No se pudo borrar la entrada %s del face swap %s', key, job_id)
        FaceSwapJob.objects.filter(id=job_id).update(**updates)
    except Exception:
        logger.exception('Falló la limpieza de entradas del face swap %s', job_id)


def _mark_faceswap_failed(job_id: str, message: str, progress: int | None = None):
    """Marca el job como fallido, libera su reserva y borra las entradas."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import release_reservation
    from apps.faceswap.models import FaceSwapJob

    updates = {
        'status': 'failed',
        'error_message': message,
        'completed_at': timezone.now(),
    }
    if progress is not None:
        updates['progress_pct'] = max(0, min(100, progress))
    updated = FaceSwapJob.objects.filter(
        id=job_id, status__in=['queued', 'processing']
    ).update(**updates)
    reservation = CreditReservation.objects.filter(
        reference_id=job_id,
        reference_type=REFERENCE_TYPE,
        status='reserved',
    ).first()
    if reservation:
        try:
            release_reservation(str(reservation.id))
        except Exception:
            logger.exception('No se pudo liberar la reserva de face swap %s', job_id)
    _cleanup_inputs(job_id)
    if updated:
        try:
            _notify_faceswap_failure(job_id, message)
        except Exception:
            logger.exception('No se pudo notificar el face swap fallido %s', job_id)


def _validate_output_object(key) -> int:
    """Verifica que el MP4 resultante exista en R2 y no esté vacío; devuelve su tamaño."""
    from ml.storage_client import get_storage_bucket, get_storage_client

    if not isinstance(key, str) or not key or not key.startswith(RESULT_PREFIX):
        raise ValueError('Modal devolvió una clave de resultado inválida.')
    metadata = get_storage_client().head_object(Bucket=get_storage_bucket(), Key=key)
    size = int(metadata.get('ContentLength', 0))
    if size <= 0:
        raise ValueError('El video resultante está vacío.')
    return size


def _settle_faceswap_credits(job) -> None:
    """Confirma la reserva del job exactamente una vez (idempotente)."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import confirm_reservation

    reservation = CreditReservation.objects.filter(
        user=job.user,
        reference_id=job.id,
        reference_type=REFERENCE_TYPE,
    ).first()
    if reservation and reservation.status == 'reserved':
        confirm_reservation(str(reservation.id))
        return
    if reservation and reservation.status == 'confirmed':
        return
    raise ValueError('La reserva de créditos fue liberada.')


@shared_task(bind=True, max_retries=3)
def process_faceswap_job(self, job_id: str):
    """Envía el job a Modal y delega su seguimiento a poll_faceswap_job."""
    from apps.faceswap.models import FaceSwapJob
    from ml.modal_client import submit_faceswap_job

    try:
        job = FaceSwapJob.objects.get(id=job_id)
        if job.status in FINAL_FACESWAP_STATES:
            return
        if job.remote_job_id:
            _schedule_faceswap_poll(job_id, countdown=0)
            return

        response = submit_faceswap_job(
            settings.MODAL_ENDPOINT_FACESWAP,
            {
                'client_job_id': str(job.id),
                'photo_s3_key': job.photo_s3_key,
                'video_s3_key': job.source_video_s3_key,
                'ref_time_s': job.ref_time_s,
                'face_x': job.target_face_x,
                'face_y': job.target_face_y,
            },
        )
        now = timezone.now()
        # Update condicional: si el job ya terminó (p. ej. fallido por la recuperación)
        # no se vuelve a activar.
        updated = FaceSwapJob.objects.filter(
            id=job_id, status__in=['queued', 'processing']
        ).update(
            remote_job_id=response['remote_job_id'],
            status='queued',
            progress_pct=0,
            started_at=now,
            error_message=None,
            updated_at=now,
        )
        if updated:
            _schedule_faceswap_poll(job_id, countdown=0)
    except Exception as exc:
        logger.exception('No se pudo iniciar el face swap %s', job_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        _mark_faceswap_failed(job_id, str(exc))


@shared_task
def recover_faceswap_job(job_id: str):
    """Reanuda un job abandonado sin iniciar un segundo job remoto."""
    from apps.faceswap.models import FaceSwapJob

    job = FaceSwapJob.objects.filter(id=job_id).first()
    if not job or job.status in FINAL_FACESWAP_STATES:
        return
    if job.remote_job_id:
        poll_faceswap_job.delay(job_id)
    else:
        process_faceswap_job.delay(job_id)


def _complete_job(job_id: str, output_key: str, size: int, progress: int) -> bool:
    """Cobra y marca completado bajo lock; devuelve True si este poll lo completó."""
    from apps.credits.services.credit_service import InsufficientCreditsError
    from apps.faceswap.models import FaceSwapJob

    with transaction.atomic():
        locked = FaceSwapJob.objects.select_for_update().select_related('user').get(id=job_id)
        if locked.status in FINAL_FACESWAP_STATES:
            return False
        try:
            _settle_faceswap_credits(locked)
        except (InsufficientCreditsError, ValueError) as exc:
            locked.status = 'failed'
            locked.progress_pct = progress
            locked.error_message = str(exc)
            locked.completed_at = timezone.now()
            locked.save(update_fields=[
                'status', 'progress_pct', 'error_message', 'completed_at', 'updated_at',
            ])
            failed = True
        else:
            locked.output_s3_key = output_key
            locked.output_file_size_bytes = size
            locked.status = 'completed'
            locked.progress_pct = 100
            locked.credits_used = settings.FACESWAP_CREDIT_COST
            locked.completed_at = timezone.now()
            locked.error_message = None
            locked.save(update_fields=[
                'output_s3_key', 'output_file_size_bytes', 'status', 'progress_pct',
                'credits_used', 'completed_at', 'error_message', 'updated_at',
            ])
            failed = False
    _cleanup_inputs(job_id)
    if failed:
        # Sin cobro no se entrega el video: se borra para no dejar caras huérfanas en R2.
        try:
            from ml.storage_client import delete_file

            delete_file(output_key)
        except Exception:
            logger.exception('No se pudo borrar el resultado no cobrado %s', output_key)
    return not failed


@shared_task(bind=True, max_retries=5)
def poll_faceswap_job(self, job_id: str):
    """Sincroniza el estado remoto de Modal con el FaceSwapJob local."""
    from apps.faceswap.models import FaceSwapJob
    from ml.modal_client import get_faceswap_job_status

    try:
        job = FaceSwapJob.objects.select_related('user').get(id=job_id)
        if job.status in FINAL_FACESWAP_STATES:
            return
        if not job.remote_job_id:
            _mark_faceswap_failed(job_id, 'El job no tiene identificador remoto.')
            return
        if job.started_at and (
            timezone.now() - job.started_at
        ).total_seconds() > settings.FACESWAP_REMOTE_TIMEOUT_SECONDS:
            _mark_faceswap_failed(
                job_id,
                'La generación excedió el tiempo máximo permitido.',
                job.progress_pct,
            )
            return

        remote = get_faceswap_job_status(settings.MODAL_ENDPOINT_FACESWAP, job.remote_job_id)
        remote_status = remote.get('status')
        progress = max(0, min(100, int(remote.get('progress_pct', job.progress_pct))))

        if remote_status in {'queued', 'processing'}:
            # Update condicional: no resucita un job que la recuperación ya marcó fallido.
            updated = FaceSwapJob.objects.filter(
                id=job_id, status__in=['queued', 'processing']
            ).update(status=remote_status, progress_pct=progress, updated_at=timezone.now())
            if updated:
                _schedule_faceswap_poll(job_id)
            return
        if remote_status == 'failed':
            _mark_faceswap_failed(
                job_id,
                remote.get('error_message') or 'Modal no pudo procesar el video.',
                progress,
            )
            return
        if remote_status != 'completed':
            _mark_faceswap_failed(job_id, f'Estado remoto desconocido: {remote_status}')
            return

        try:
            size = _validate_output_object(remote.get('output_s3_key'))
        except Exception as exc:
            _mark_faceswap_failed(job_id, str(exc), progress)
            return

        if not _complete_job(job_id, remote['output_s3_key'], size, progress):
            failed_job = FaceSwapJob.objects.filter(
                id=job_id, status='failed'
            ).first()
            if failed_job:
                try:
                    _notify_faceswap_failure(job_id, failed_job.error_message or 'No se pudo completar el video.')
                except Exception:
                    logger.exception('No se pudo notificar el face swap fallido %s', job_id)
            return
        try:
            from apps.notifications.services import notify_user

            notify_user(job.user, type='faceswap_ready', reference_id=str(job.id))
        except Exception:
            logger.exception('No se pudo notificar el face swap %s', job.id)
    except Exception as exc:
        logger.exception('Error consultando el face swap %s', job_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=min(60, 10 * (self.request.retries + 1)))
        _mark_faceswap_failed(job_id, str(exc))
