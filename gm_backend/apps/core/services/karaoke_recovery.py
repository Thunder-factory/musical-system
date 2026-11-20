"""Rescate específico para KaraokeTrack compartido entre varios usuarios."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone


def recover_karaoke_track(track, stale_before, remote_state_value: str) -> tuple[str, int]:
    """Recupera un KaraokeTrack compartido evaluando las reservas de todos sus usuarios."""
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
            f'Estado remoto: {remote_state_value}.'
        )
        current.save(update_fields=[
            'status', 'processing_stage', 'error_message', 'updated_at',
        ])
        return 'failed', released_count
