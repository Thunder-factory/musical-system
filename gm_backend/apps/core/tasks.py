"""Periodic recovery tasks for asynchronous operations.

These tasks only requeue stale work.  They never close a recent operation,
and each domain task keeps its own idempotency and remote-job checks.
"""

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone


def _stale(seconds_name: str, default: int = 1800):
    return timezone.now() - timedelta(
        seconds=getattr(settings, seconds_name, default)
    )


@shared_task
def recover_abandoned_operations():
    """Requeue abandoned local work and release expired reservations."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import release_reservation
    from apps.karaoke.models import KaraokeTrack
    from apps.mix.models import MixExport
    from apps.songs.models import GenerationJob
    from apps.stems.models import StemJob

    now = timezone.now()
    recovered = {
        'songs': 0,
        'karaoke': 0,
        'stems': 0,
        'mix': 0,
        'reservations': 0,
    }

    generation_stale = _stale('GENERATION_PROCESSING_STALE_SECONDS')
    for job in GenerationJob.objects.filter(
        Q(status='queued', updated_at__lt=generation_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=generation_stale)
        | Q(status='processing', started_at__lt=generation_stale)
    ):
        from apps.songs.tasks import process_generation_job
        process_generation_job.delay(str(job.id))
        recovered['songs'] += 1

    for track in KaraokeTrack.objects.filter(
        status__in=['queued', 'processing'],
    ).filter(
        updated_at__lt=_stale('KARAOKE_PROCESSING_STALE_SECONDS'),
    ):
        from apps.karaoke.tasks import poll_karaoke_track
        poll_karaoke_track.delay(str(track.id))
        recovered['karaoke'] += 1

    stem_stale = _stale('STEM_REMOTE_TIMEOUT_SECONDS')
    for job in StemJob.objects.filter(
        Q(status='queued', updated_at__lt=stem_stale)
        | Q(status='processing', started_at__isnull=True, updated_at__lt=stem_stale)
        | Q(status='processing', started_at__lt=stem_stale)
    ):
        from apps.stems.tasks import recover_stem_job
        recover_stem_job.delay(str(job.id))
        recovered['stems'] += 1

    for export in MixExport.objects.filter(status__in=['queued', 'processing']).filter(
        updated_at__lt=_stale('MIX_EXPORT_PROCESSING_STALE_SECONDS'),
    ):
        from apps.mix.tasks import render_mix
        render_mix.delay(str(export.id))
        recovered['mix'] += 1

    for reservation in CreditReservation.objects.filter(
        status='reserved', expires_at__isnull=False, expires_at__lte=now,
    ).values_list('id', flat=True):
        try:
            release_reservation(str(reservation))
            recovered['reservations'] += 1
        except CreditReservation.DoesNotExist:
            continue

    return recovered
