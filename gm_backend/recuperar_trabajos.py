
from django.db import transaction
from django.utils import timezone

from apps.songs.models import Song, GenerationJob
from apps.karaoke.models import KaraokeTrack
from apps.credits.models import CreditReservation, CreditTransaction
from apps.credits.services.credit_service import release_reservation

# Simulacion False para recuperar
DRY_RUN = False

GENERATION_ID = "6d78f10a-d0f5-4214-86bb-5525ecfcf867"
SONG_ID = "c04b739e-2c90-4fde-9d2f-4373a4af9734"
KARAOKE_ID = "35d2df2a-7554-4283-a96a-048d24d0b276"

with transaction.atomic():
    job = GenerationJob.objects.select_for_update().get(
        id=GENERATION_ID
    )
    song = Song.objects.select_for_update().get(id=SONG_ID)
    karaoke = KaraokeTrack.objects.select_for_update().get(
        id=KARAOKE_ID
    )

    reservations = list(
        CreditReservation.objects.select_for_update().filter(
            reference_id__in=[GENERATION_ID, KARAOKE_ID]
        )
    )

    if job.status != "processing":
        raise RuntimeError("La generación cambió de estado.")

    if job.song_id != song.id or song.status != "processing":
        raise RuntimeError("La canción cambió de estado.")

    if song.audio_s3_key or song.thumbnail_s3_key:
        raise RuntimeError("La canción tiene archivos asociados.")

    if job.remote_result or job.completed_at:
        raise RuntimeError("La generación tiene un resultado remoto.")

    if karaoke.status not in ("queued", "processing"):
        raise RuntimeError("El Karaoke cambió de estado.")

    if karaoke.instrumental_s3_key or karaoke.vocals_s3_key:
        raise RuntimeError("El Karaoke tiene pistas asociadas.")

    expected = {
        (str(job.id), "generation_job"): 1,
        (str(karaoke.id), "karaoke_access"): 2,
    }

    actual = {
        (str(r.reference_id), r.reference_type): r.amount
        for r in reservations
    }

    if actual != expected or len(reservations) != 2:
        raise RuntimeError("Las reservas no coinciden.")

    if any(r.status != "reserved" for r in reservations):
        raise RuntimeError("Hay reservas que ya no están pendientes.")

    if CreditTransaction.objects.filter(
        reference_id__in=[GENERATION_ID, KARAOKE_ID]
    ).exists():
        raise RuntimeError("Existen transacciones asociadas.")

    print("Verificaciones locales correctas.")
    print("Reservas a liberar:", sum(r.amount for r in reservations))

    if DRY_RUN:
        print("SIMULACIÓN: no se modificó ningún registro.")
    else:
        job.status = "failed"
        job.error_message = "Generación abandonada; recuperación administrativa."
        job.completed_at = timezone.now()
        job.save(update_fields=[
            "status", "error_message", "completed_at", "updated_at"
        ])

        song.status = "failed"
        song.save(update_fields=["status", "updated_at"])

        karaoke.status = "failed"
        karaoke.error_message = (
            "Tarea interrumpida; recuperación administrativa."
        )
        karaoke.processed_at = timezone.now()
        karaoke.save(update_fields=[
            "status", "error_message", "processed_at", "updated_at"
        ])

        for reservation in reservations:
            release_reservation(str(reservation.id))

        print("Trabajos cerrados y reservas liberadas.")
