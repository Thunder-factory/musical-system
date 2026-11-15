from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from apps.credits.models import CreditReservation
from apps.credits.services.credit_service import (
    InsufficientCreditsError as CreditInsufficientCreditsError,
    check_balance,
    deduct_credits,
    reserve_credits,
)
from apps.karaoke.models import KaraokeTrack, UserKaraokeAccess
from apps.songs.models import Song

if TYPE_CHECKING:
    from apps.users.models import User

KARAOKE_CREDIT_COST = 2


class InsufficientCreditsError(Exception):
    """El usuario no tiene suficientes créditos para generar karaoke."""


class SongNotEligibleError(Exception):
    """La canción no cumple los requisitos para karaoke."""


def request_karaoke(user: User, song_id: str) -> tuple[KaraokeTrack, bool]:
    """
    Orquesta el flujo de solicitud de karaoke para una canción.

    Returns:
        (karaoke_track, already_owned)
        already_owned=True cuando el usuario ya tenía acceso y no se cobró nada.

    Raises:
        Song.DoesNotExist: Si la canción no existe.
        SongNotEligibleError: Si la canción no es apta para karaoke.
        InsufficientCreditsError: Si el usuario no tiene créditos suficientes.
    """
    song = Song.objects.get(id=song_id)

    if song.status != 'ready':
        raise SongNotEligibleError("La canción todavía no está lista.")
    if song.instrumental:
        raise SongNotEligibleError("Las canciones instrumentales no tienen voz para sincronizar.")

    with transaction.atomic():
        track = KaraokeTrack.objects.select_for_update().filter(song=song).first()

        # Un track fallido debe poder regenerarse incluso si dejó un acceso
        # pendiente del intento anterior.
        if track is not None and track.status == 'failed':
            for access in track.user_accesses.filter(credits_paid=0):
                reservation = CreditReservation.objects.filter(
                    user_id=access.user_id,
                    reference_id=track.id,
                    reference_type='karaoke_access',
                    status='reserved',
                ).first()
                if reservation:
                    from apps.credits.services.credit_service import release_reservation
                    release_reservation(str(reservation.id))
            track.delete()
            track = None

        # Caso C: el usuario ya tiene acceso — sin cobro
        if track is not None:
            already_owned = UserKaraokeAccess.objects.filter(
                user=user, karaoke_track=track
            ).exists()
            if already_owned:
                return track, True

        # Se valida el saldo al solicitar la operación. El descuento del
        # primer procesamiento se realiza cuando la tarea termina bien.
        if track is None:
            # Caso A: primer procesamiento — crear track y encolar tarea.
            # El acceso queda pendiente hasta que Demucs/Modal termine.
            track = KaraokeTrack.objects.create(song=song, status='queued')
            UserKaraokeAccess.objects.create(user=user, karaoke_track=track, credits_paid=0)
            try:
                reserve_credits(
                    user,
                    amount=KARAOKE_CREDIT_COST,
                    reference_id=str(track.id),
                    reference_type='karaoke_access',
                )
            except CreditInsufficientCreditsError as exc:
                raise InsufficientCreditsError(str(exc)) from exc
            # Encolar después del commit para garantizar que el registro ya existe en DB
            transaction.on_commit(
                lambda tid=str(track.id): _enqueue_generation(tid)
            )
        elif track.status == 'ready':
            # Caso B: karaoke ya listo — se concede acceso y se cobra de inmediato.
            if not check_balance(user, required=KARAOKE_CREDIT_COST):
                raise InsufficientCreditsError(
                    f"Necesitas {KARAOKE_CREDIT_COST} créditos para acceder al karaoke."
                )
            deduct_credits(
                user,
                KARAOKE_CREDIT_COST,
                reference_id=str(track.id),
                reference_type='karaoke',
            )
            UserKaraokeAccess.objects.create(
                user=user, karaoke_track=track, credits_paid=KARAOKE_CREDIT_COST
            )
        else:
            # Caso C: otro usuario ya está generando el karaoke. Se espera a
            # que la tarea termine para cobrar este acceso pendiente.
            UserKaraokeAccess.objects.create(user=user, karaoke_track=track, credits_paid=0)
            try:
                reserve_credits(
                    user,
                    amount=KARAOKE_CREDIT_COST,
                    reference_id=str(track.id),
                    reference_type='karaoke_access',
                )
            except CreditInsufficientCreditsError as exc:
                raise InsufficientCreditsError(str(exc)) from exc

    return track, False


def _enqueue_generation(karaoke_track_id: str) -> None:
    from apps.karaoke.tasks import generate_karaoke_track
    generate_karaoke_track.delay(karaoke_track_id)
