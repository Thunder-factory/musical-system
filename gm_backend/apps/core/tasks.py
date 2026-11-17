"""Recovery tasks for abandoned asynchronous operations."""

from datetime import timedelta
import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def _stale(seconds_name: str, default: int = 1800):
    return timezone.now() - timedelta(
        seconds=getattr(settings, seconds_name, default)
    )


def _remote_state(
    kind: str,
    remote_job_id: str | None,
    endpoint_url: str | None = None,
) -> str:
    """Return a best-effort remote state without holding database locks."""
    if not remote_job_id:
        return 'unknown'
    if kind == 'generation' and not endpoint_url:
        return 'unavailable'
    try:
        if kind == 'generation':
            from ml.modal_client import get_music_job_status

            response = get_music_job_status(endpoint_url, remote_job_id)
        else:
            from ml.modal_client import get_stem_job_status

            response = get_stem_job_status(
                settings.MODAL_ENDPOINT_SEPARATE_STEMS,
                remote_job_id,
            )
        return response.get('status') or 'unknown'
    except Exception:
        logger.exception(
            'No se pudo consultar el trabajo remoto durante la recuperación: %s %s',
            kind,
            remote_job_id,
        )
        return 'unavailable'


def _cleanup_unreferenced_storage_keys(keys):
    """Remove only persisted output keys that have no database reference."""
    from apps.songs.models import Song
    from ml.storage_client import delete_file

    for key in {key for key in keys if key}:
        if Song.objects.filter(
            Q(audio_s3_key=key) | Q(thumbnail_s3_key=key)
        ).exists():
            continue
        try:
            delete_file(key)
        except Exception:
            logger.exception('No se pudo limpiar el archivo huérfano %s', key)


def _recover_one(
    *,
    model,
    object_id,
    user_id,
    reference_type: str,
    stale_check,
    enqueue,
    remote_state: str,
    failure_message: str,
    final_statuses: set[str],
    on_failed=None,
    cleanup_failed=None,
) -> tuple[str, int]:
    """Recover one object using a short, consistently ordered transaction."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import release_reservation
    from apps.users.models import User

    action = 'ignored'
    released_count = 0
    with transaction.atomic():
        # The candidate query is only a hint; always re-read under the lock.
        locked_user = User.objects.select_for_update().get(pk=user_id)
        operation = model.objects.select_for_update().get(pk=object_id)
        if operation.status in final_statuses or not stale_check(operation):
            return 'ignored', 0

        reservation = CreditReservation.objects.select_for_update().filter(
            user=locked_user,
            reference_id=object_id,
            reference_type=reference_type,
        ).first()
        now = timezone.now()
        reservation_valid = bool(
            reservation and reservation.status == 'confirmed'
        ) or bool(
            reservation
            and reservation.status == 'reserved'
            and (reservation.expires_at is None or reservation.expires_at > now)
        )

        if reservation_valid:
            operation.status = 'queued'
            updates = ['status', 'updated_at']
            if hasattr(operation, 'error_message'):
                operation.error_message = None
                updates.append('error_message')
            operation.save(update_fields=updates)
            action = 'requeue'
        else:
            if reservation and reservation.status == 'reserved':
                # Idempotent and does not create a debit transaction.
                release_reservation(str(reservation.id))
                released_count = 1

            operation.status = 'failed'
            updates = ['status', 'updated_at']
            if hasattr(operation, 'error_message'):
                operation.error_message = (
                    f'{failure_message} Estado remoto: {remote_state}.'
                )
                updates.append('error_message')
            if hasattr(operation, 'completed_at'):
                operation.completed_at = now
                updates.append('completed_at')
            operation.save(update_fields=updates)
            if on_failed:
                on_failed()
            action = 'failed'

    if action == 'requeue':
        # This runs after commit, so a worker cannot observe a half-written
        # state and a second recovery sees the refreshed updated_at.
        enqueue()
    elif action == 'failed' and cleanup_failed:
        cleanup_failed()
    return action, released_count


def _recover_karaoke_track(track, stale_before, remote_state):
    """Recover a shared KaraokeTrack using all users' access reservations."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import release_reservation
    from apps.karaoke.models import KaraokeTrack, UserKaraokeAccess
    from apps.users.models import User

    released_count = 0
    with transaction.atomic():
        current = KaraokeTrack.objects.select_for_update().get(pk=track.id)
        if current.status in {'ready', 'failed'} or current.updated_at >= stale_before:
            return 'ignored', 0

        reservations = list(CreditReservation.objects.filter(
            reference_id=current.id,
            reference_type='karaoke_access',
        ).order_by('user_id').values('id', 'user_id', 'status', 'expires_at'))
        user_ids = sorted({reservation['user_id'] for reservation in reservations})
        if user_ids:
            list(User.objects.select_for_update().filter(id__in=user_ids).order_by('id'))
        locked_reservations = {
            reservation.id: reservation
            for reservation in CreditReservation.objects.select_for_update().filter(
                reference_id=current.id,
                reference_type='karaoke_access',
            )
        }
        now = timezone.now()
        valid = any(
            reservation.status == 'confirmed'
            or (
                reservation.status == 'reserved'
                and (reservation.expires_at is None or reservation.expires_at > now)
            )
            for reservation in locked_reservations.values()
        )

        if valid:
            current.status = 'queued'
            current.processing_stage = 'queued'
            current.error_message = None
            current.save(update_fields=[
                'status', 'processing_stage', 'error_message', 'updated_at',
            ])
            return 'requeue', 0

        for reservation in locked_reservations.values():
            if reservation.status == 'reserved':
                release_reservation(str(reservation.id))
                released_count += 1
        UserKaraokeAccess.objects.filter(
            karaoke_track=current,
            credits_paid=0,
        ).delete()
        current.status = 'failed'
        current.processing_stage = 'failed'
        current.error_message = (
            'El trabajo de Karaoke abandonado no tiene acceso confirmable. '
            f'Estado remoto: {remote_state}.'
        )
        current.save(update_fields=[
            'status', 'processing_stage', 'error_message', 'updated_at',
        ])
        return 'failed', released_count


@shared_task
def recover_abandoned_operations():
    """Close unrecoverable stale work and requeue only billable work."""
    from apps.karaoke.models import KaraokeTrack
    from apps.mix.models import MixExport, MixProject
    from apps.songs.models import GenerationJob, Song
    from apps.stems.models import StemJob

    recovered = {
        'songs': 0,
        'karaoke': 0,
        'stems': 0,
        'mix': 0,
        'failed': 0,
        'reservations': 0,
    }

    generation_stale = _stale('GENERATION_PROCESSING_STALE_SECONDS')
    for job in GenerationJob.objects.filter(
        Q(status='queued', updated_at__lt=generation_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=generation_stale)
        | Q(status='processing', started_at__lt=generation_stale)
    ).values(
        'id', 'user_id', 'song_id', 'modal_endpoint_used',
        'remote_job_id', 'remote_result',
    ):
        action, released = _recover_one(
            model=GenerationJob,
            object_id=job['id'],
            user_id=job['user_id'],
            reference_type='generation_job',
            stale_check=lambda operation: (
                operation.status == 'queued'
                and operation.updated_at < generation_stale
            ) or (
                operation.status == 'processing'
                and (
                    operation.updated_at < generation_stale
                    or (
                        operation.started_at is not None
                        and operation.started_at < generation_stale
                    )
                )
            ),
            enqueue=lambda job_id=str(job['id']): __import__(
                'apps.songs.tasks', fromlist=['process_generation_job']
            ).process_generation_job.delay(job_id),
            remote_state=_remote_state(
                'generation',
                job['remote_job_id'],
                job['modal_endpoint_used'],
            ) if job['remote_job_id'] else (
                'completed' if job['remote_result']
                else 'unknown'
            ),
            failure_message='La generación abandonada no tiene una reserva confirmable.',
            final_statuses={'completed', 'failed', 'no_credits'},
            on_failed=lambda song_id=job['song_id']: Song.objects.select_for_update().filter(
                id=song_id
            ).update(status='failed'),
            cleanup_failed=lambda result=job['remote_result']: _cleanup_unreferenced_storage_keys(
                [
                    result.get('s3_key'),
                    result.get('cover_image_s3_key'),
                ] if result else []
            ),
        )
        if action == 'failed':
            recovered['failed'] += 1
        elif action == 'requeue':
            recovered['songs'] += 1
        recovered['reservations'] += released

    karaoke_stale = _stale('KARAOKE_PROCESSING_STALE_SECONDS')
    for track in KaraokeTrack.objects.filter(
        status__in=['queued', 'processing'],
        updated_at__lt=karaoke_stale,
    ).select_related('song'):
        action, released = _recover_karaoke_track(
            track,
            karaoke_stale,
            _remote_state('karaoke', track.remote_job_id),
        )
        if action == 'requeue':
            __import__('apps.karaoke.tasks', fromlist=['poll_karaoke_track']).poll_karaoke_track.delay(
                str(track.id)
            )
            recovered['karaoke'] += 1
        elif action == 'failed':
            recovered['failed'] += 1
        recovered['reservations'] += released

    stem_stale = _stale('STEM_REMOTE_TIMEOUT_SECONDS')
    for job in StemJob.objects.filter(
        Q(status='queued', updated_at__lt=stem_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=stem_stale)
        | Q(status='processing', started_at__lt=stem_stale)
    ).values('id', 'user_id', 'remote_job_id'):
        action, released = _recover_one(
            model=StemJob,
            object_id=job['id'],
            user_id=job['user_id'],
            reference_type='stem_job',
            stale_check=lambda operation: (
                operation.status == 'queued'
                and operation.updated_at < stem_stale
            ) or (
                operation.status == 'processing'
                and (
                    operation.updated_at < stem_stale
                    or (
                        operation.started_at is not None
                        and operation.started_at < stem_stale
                    )
                )
            ),
            enqueue=lambda job_id=str(job['id']): __import__(
                'apps.stems.tasks', fromlist=['recover_stem_job']
            ).recover_stem_job.delay(job_id),
            remote_state=_remote_state('stems', job['remote_job_id']),
            failure_message='La separación de stems abandonada no tiene una reserva confirmable.',
            final_statuses={'completed', 'failed'},
        )
        if action == 'requeue':
            recovered['stems'] += 1
        elif action == 'failed':
            recovered['failed'] += 1
        recovered['reservations'] += released

    mix_stale = _stale('MIX_EXPORT_PROCESSING_STALE_SECONDS')
    for export in MixExport.objects.filter(
        status__in=['queued', 'processing'],
        updated_at__lt=mix_stale,
    ).select_related('mix_project'):
        action, released = _recover_one(
            model=MixExport,
            object_id=export.id,
            user_id=export.mix_project.user_id,
            reference_type='mix_export',
            stale_check=lambda operation: (
                operation.status in {'queued', 'processing'}
                and operation.updated_at < mix_stale
            ),
            enqueue=lambda export_id=str(export.id): __import__(
                'apps.mix.tasks', fromlist=['render_mix']
            ).render_mix.delay(export_id),
            remote_state='completed' if export.output_s3_key else 'unknown',
            failure_message='La exportación de Mix abandonada no tiene una reserva confirmable.',
            final_statuses={'ready', 'failed'},
            on_failed=lambda project_id=export.mix_project_id: MixProject.objects.select_for_update().filter(
                id=project_id
            ).update(status='failed'),
            cleanup_failed=lambda key=export.output_s3_key: _cleanup_unreferenced_storage_keys(
                [key]
            ),
        )
        if action == 'requeue':
            recovered['mix'] += 1
        elif action == 'failed':
            recovered['failed'] += 1
        recovered['reservations'] += released

    return recovered
