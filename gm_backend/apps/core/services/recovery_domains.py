"""Rescate de operaciones asíncronas de música, karaoke, stems, faceswap y mix."""

from __future__ import annotations

from django.db.models import Q

from apps.core.services.karaoke_recovery import recover_karaoke_track
from apps.core.services.recovery_helpers import (
    cleanup_unreferenced_storage_keys,
    recover_one,
    remote_state,
    stale_cutoff,
)


def recover_songs(recovered: dict) -> None:
    from apps.songs.models import GenerationJob, Song

    generation_stale = stale_cutoff('GENERATION_PROCESSING_STALE_SECONDS')
    for job in GenerationJob.objects.filter(
        Q(status='queued', updated_at__lt=generation_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=generation_stale)
        | Q(status='processing', started_at__lt=generation_stale)
    ).values(
        'id', 'user_id', 'song_id', 'modal_endpoint_used',
        'remote_job_id', 'remote_result',
    ):
        action, released = recover_one(
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
            remote_state=remote_state(
                'generation',
                job['remote_job_id'],
                job['modal_endpoint_used'],
            ) if job['remote_job_id'] else (
                'completed' if job['remote_result'] else 'unknown'
            ),
            failure_message='La generación abandonada no tiene una reserva confirmable.',
            final_statuses={'completed', 'failed', 'no_credits'},
            on_failed=lambda song_id=job['song_id']: Song.objects.select_for_update().filter(
                id=song_id
            ).update(status='failed'),
            cleanup_failed=lambda result=job['remote_result']: cleanup_unreferenced_storage_keys(
                [result.get('s3_key'), result.get('cover_image_s3_key')] if result else []
            ),
        )
        if action == 'failed':
            recovered['failed'] += 1
        elif action == 'requeue':
            recovered['songs'] += 1
        recovered['reservations'] += released


def recover_karaoke(recovered: dict) -> None:
    from apps.karaoke.models import KaraokeTrack

    karaoke_stale = stale_cutoff('KARAOKE_PROCESSING_STALE_SECONDS')
    for track in KaraokeTrack.objects.filter(
        status__in=['queued', 'processing'],
        updated_at__lt=karaoke_stale,
    ).select_related('song'):
        action, released = recover_karaoke_track(
            track,
            karaoke_stale,
            remote_state('karaoke', track.remote_job_id),
        )
        if action == 'requeue':
            __import__('apps.karaoke.tasks', fromlist=['poll_karaoke_track']).poll_karaoke_track.delay(
                str(track.id)
            )
            recovered['karaoke'] += 1
        elif action == 'failed':
            recovered['failed'] += 1
        recovered['reservations'] += released


def recover_stems(recovered: dict) -> None:
    from apps.stems.models import StemJob

    stem_stale = stale_cutoff('STEM_REMOTE_TIMEOUT_SECONDS')
    for job in StemJob.objects.filter(
        Q(status='queued', updated_at__lt=stem_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=stem_stale)
        | Q(status='processing', started_at__lt=stem_stale)
    ).values('id', 'user_id', 'remote_job_id'):
        action, released = recover_one(
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
            remote_state=remote_state('stems', job['remote_job_id']),
            failure_message='La separación de stems abandonada no tiene una reserva confirmable.',
            final_statuses={'completed', 'failed'},
        )
        if action == 'requeue':
            recovered['stems'] += 1
        elif action == 'failed':
            recovered['failed'] += 1
        recovered['reservations'] += released


def recover_faceswap(recovered: dict) -> None:
    from apps.faceswap.models import FaceSwapJob

    faceswap_stale = stale_cutoff('FACESWAP_REMOTE_TIMEOUT_SECONDS')
    for job in FaceSwapJob.objects.filter(
        Q(status='queued', updated_at__lt=faceswap_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=faceswap_stale)
        | Q(status='processing', started_at__lt=faceswap_stale),
        deleted_at__isnull=True,
    ).values('id', 'user_id', 'remote_job_id'):
        action, released = recover_one(
            model=FaceSwapJob,
            object_id=job['id'],
            user_id=job['user_id'],
            reference_type='faceswap_job',
            stale_check=lambda operation: (
                operation.status == 'queued'
                and operation.updated_at < faceswap_stale
            ) or (
                operation.status == 'processing'
                and (
                    operation.updated_at < faceswap_stale
                    or (
                        operation.started_at is not None
                        and operation.started_at < faceswap_stale
                    )
                )
            ),
            enqueue=lambda job_id=str(job['id']): __import__(
                'apps.faceswap.tasks', fromlist=['recover_faceswap_job']
            ).recover_faceswap_job.delay(job_id),
            remote_state=remote_state('faceswap', job['remote_job_id']),
            failure_message='El face swap abandonado no tiene una reserva confirmable.',
            final_statuses={'completed', 'failed'},
            cleanup_failed=lambda job_id=str(job['id']): __import__(
                'apps.faceswap.tasks', fromlist=['_cleanup_inputs']
            )._cleanup_inputs(job_id),
        )
        if action == 'requeue':
            recovered['faceswap'] += 1
        elif action == 'failed':
            recovered['failed'] += 1
        recovered['reservations'] += released


def recover_mix(recovered: dict) -> None:
    from apps.mix.models import MixExport, MixProject

    mix_stale = stale_cutoff('MIX_EXPORT_PROCESSING_STALE_SECONDS')
    for export in MixExport.objects.filter(
        status__in=['queued', 'processing'],
        updated_at__lt=mix_stale,
    ).select_related('mix_project'):
        action, released = recover_one(
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
            cleanup_failed=lambda key=export.output_s3_key: cleanup_unreferenced_storage_keys([key]),
        )
        if action == 'requeue':
            recovered['mix'] += 1
        elif action == 'failed':
            recovered['failed'] += 1
        recovered['reservations'] += released
