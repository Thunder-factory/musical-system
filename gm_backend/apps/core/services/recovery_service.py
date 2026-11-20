"""Orquestación de rescate para operaciones asíncronas abandonadas."""

from __future__ import annotations

from django.db.models import Q

from apps.core.services.recovery_domains import (
    recover_faceswap,
    recover_karaoke,
    recover_mix,
    recover_songs,
    recover_stems,
)
from apps.core.services.recovery_helpers import fail_stale_operation, stale_cutoff


def _recover_humming(recovered: dict) -> None:
    from apps.humming.models import HummingEnhancement, HummingJob

    queue_stale = stale_cutoff('HUMMING_QUEUE_STALE_SECONDS', 1800)
    proc_stale = stale_cutoff('HUMMING_PROCESSING_STALE_SECONDS', 1200)
    for job in HummingJob.objects.filter(
        Q(status='queued', updated_at__lt=queue_stale)
        | Q(status='queued', created_at__lt=queue_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=proc_stale)
        | Q(status='processing', started_at__lt=proc_stale)
    ).values('id', 'user_id'):
        action, released = fail_stale_operation(
            model=HummingJob,
            object_id=job['id'],
            user_id=job['user_id'],
            reference_type='humming_job',
            stale_check=lambda op: (
                (op.status == 'queued' and (op.updated_at < queue_stale or op.created_at < queue_stale))
                or (
                    op.status == 'processing'
                    and (
                        (op.started_at is None and op.updated_at < proc_stale)
                        or (op.started_at is not None and op.started_at < proc_stale)
                    )
                )
            ),
            failure_message='El tarareo abandonado excedió el tiempo máximo permitido.',
            final_statuses=set(HummingJob.TERMINAL_STATUSES),
            extra_updates={'error_code': 'TIEMPO_AGOTADO'},
        )
        if action == 'failed':
            recovered['humming'] += 1
            recovered['failed'] += 1
        recovered['reservations'] += released

    enhance_stale = stale_cutoff('HUMMING_ENHANCE_STALE_SECONDS', 1800)
    for item in HummingEnhancement.objects.filter(
        Q(status='queued', updated_at__lt=enhance_stale)
        | Q(status='queued', created_at__lt=enhance_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=enhance_stale)
        | Q(status='processing', started_at__lt=enhance_stale)
    ).values('id', 'user_id'):
        action, released = fail_stale_operation(
            model=HummingEnhancement,
            object_id=item['id'],
            user_id=item['user_id'],
            reference_type='humming_enhancement',
            stale_check=lambda op: (
                (op.status == 'queued' and (op.updated_at < enhance_stale or op.created_at < enhance_stale))
                or (
                    op.status == 'processing'
                    and (
                        (op.started_at is None and op.updated_at < enhance_stale)
                        or (op.started_at is not None and op.started_at < enhance_stale)
                    )
                )
            ),
            failure_message='La mejora con IA abandonada excedió el tiempo máximo permitido.',
            final_statuses=set(HummingEnhancement.TERMINAL_STATUSES),
        )
        if action == 'failed':
            recovered['humming_enhancements'] += 1
            recovered['failed'] += 1
        recovered['reservations'] += released


def _recover_translations(recovered: dict) -> None:
    from apps.translations.models import TranslationJob

    translation_stale = stale_cutoff('TRANSLATION_REMOTE_TIMEOUT_SECONDS', 2400)
    for job in TranslationJob.objects.filter(
        Q(status='queued', updated_at__lt=translation_stale)
        | Q(status='queued', created_at__lt=translation_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=translation_stale)
        | Q(status='processing', started_at__lt=translation_stale)
    ).values('id', 'user_id'):
        action, released = fail_stale_operation(
            model=TranslationJob,
            object_id=job['id'],
            user_id=job['user_id'],
            reference_type='translation_job',
            stale_check=lambda op: (
                (op.status == 'queued' and (op.updated_at < translation_stale or op.created_at < translation_stale))
                or (
                    op.status == 'processing'
                    and (
                        (op.started_at is None and op.updated_at < translation_stale)
                        or (op.started_at is not None and op.started_at < translation_stale)
                    )
                )
            ),
            failure_message='La traducción abandonada excedió el tiempo máximo permitido.',
            final_statuses={'completed', 'failed'},
        )
        if action == 'failed':
            recovered['translations'] += 1
            recovered['failed'] += 1
        recovered['reservations'] += released


def recover_abandoned_operations_service() -> dict:
    """Ejecuta el rescate de operaciones abandonadas en todos los dominios del sistema."""
    recovered = {
        'songs': 0,
        'karaoke': 0,
        'stems': 0,
        'mix': 0,
        'faceswap': 0,
        'humming': 0,
        'humming_enhancements': 0,
        'translations': 0,
        'failed': 0,
        'reservations': 0,
    }
    recover_songs(recovered)
    recover_karaoke(recovered)
    recover_stems(recovered)
    recover_faceswap(recovered)
    recover_mix(recovered)
    _recover_humming(recovered)
    _recover_translations(recovered)
    return recovered
