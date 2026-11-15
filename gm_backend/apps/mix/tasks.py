import logging

from celery import shared_task
from django.db import transaction
import pydub
import os
from decouple import config

logger = logging.getLogger(__name__)


def _ensure_mix_song(mix, user, s3_key, duration_seconds, tag_ids, clips):
    """Crea la canción derivada bajo bloqueo del mix para evitar duplicados."""
    from django.db import transaction
    from apps.songs.models import Song, SongTag, Tag

    with transaction.atomic():
        locked_mix = mix.__class__.objects.select_for_update().get(pk=mix.pk)
        song = Song.objects.filter(audio_s3_key=s3_key).first()
        if song:
            return song

        song = Song.objects.create(
            user=user,
            title=locked_mix.title,
            description=locked_mix.description or 'Mezcla creada en Mix DJ.',
            audio_duration=float(duration_seconds),
            audio_s3_key=s3_key,
            status='ready',
            lyrics_source='user',
        )
        first_clip_with_thumb = (
            clips.filter(song__isnull=False, song__thumbnail_s3_key__isnull=False)
            .exclude(song__thumbnail_s3_key='')
            .select_related('song')
            .first()
        )
        if first_clip_with_thumb:
            song.thumbnail_s3_key = first_clip_with_thumb.song.thumbnail_s3_key
            song.save(update_fields=['thumbnail_s3_key'])

        if tag_ids:
            tags_to_assign = list(Tag.objects.filter(id__in=tag_ids))
        else:
            first_clip_with_song = (
                clips.filter(song__isnull=False)
                .select_related('song')
                .prefetch_related('song__tags')
                .first()
            )
            tags_to_assign = list(first_clip_with_song.song.tags.all()) if first_clip_with_song else []
        for tag in tags_to_assign:
            SongTag.objects.get_or_create(song=song, tag=tag)
        return song

ffmpeg_path = config('FFMPEG_PATH', default=None)
if ffmpeg_path:
    pydub.AudioSegment.converter = ffmpeg_path


@shared_task(bind=True, max_retries=2)
def render_mix(self, export_id: str, tag_ids: list = None):
    from apps.mix.models import MixExport, MixClip
    from apps.mix.services.audio_editor import (
        download_audio_from_storage, apply_clip_effects, get_clip_storage_key,
    )
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import (
        InsufficientCreditsError,
        confirm_reservation,
        check_balance,
        deduct_credits,
        release_reservation,
    )
    from apps.songs.models import Song
    from pydub import AudioSegment
    from ml.storage_client import upload_file, delete_file
    import tempfile
    import os

    uploaded_key = None
    try:
        with transaction.atomic():
            export = MixExport.objects.select_for_update().select_related(
                'mix_project__user'
            ).get(id=export_id)
            if export.status == 'ready' and export.output_s3_key:
                return
            if export.status == 'processing':
                # Otra ejecución conserva la propiedad del export. Cuando
                # falla, el bloque exterior lo devuelve a queued antes del retry.
                return
            export.status = 'processing'
            export.save(update_fields=['status'])
        mix    = export.mix_project
        user   = mix.user

        reservation = CreditReservation.objects.filter(
            user=user,
            reference_id=export.id,
            reference_type='mix_export',
        ).first()
        if reservation and reservation.status == 'released':
            raise ValueError('La reserva de créditos del mix fue liberada.')
        if not reservation and export.credits_used == 0 and not check_balance(user, required=3):
            export.status = 'failed'
            export.error_message = 'Sin créditos suficientes (se necesitan 3).'
            export.save(update_fields=['status', 'error_message'])
            return

        clips = MixClip.objects.filter(mix_project=mix).order_by('position')
        if not clips.exists():
            raise ValueError("El mix no tiene clips.")

        final_audio = AudioSegment.empty()
        for clip in clips:
            object_key = get_clip_storage_key(clip)
            audio_path = download_audio_from_storage(object_key)
            try:
                audio     = AudioSegment.from_file(audio_path)
                processed = apply_clip_effects(audio, clip)
                final_audio += processed
            finally:
                os.unlink(audio_path)

        output_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=f'.{export.format}', delete=False) as tmp:
                bitrate = export.quality if export.format == 'mp3' else None
                output_path = tmp.name
            final_audio.export(output_path, format=export.format, bitrate=bitrate)

            s3_key = f"mix-exports/{mix.id}/{export.id}.{export.format}"
            upload_file(output_path, s3_key)
            uploaded_key = s3_key
        finally:
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)

        duration_seconds = len(final_audio) // 1000

        _ensure_mix_song(mix, user, s3_key, duration_seconds, tag_ids, clips)

        try:
            if reservation and reservation.status == 'reserved':
                confirm_reservation(str(reservation.id))
            elif reservation and reservation.status == 'confirmed':
                pass
            elif not reservation and export.credits_used == 0:
                deduct_credits(user, amount=3, reference_id=str(export.id), reference_type='mix_export')
        except InsufficientCreditsError as exc:
            if reservation and reservation.status == 'reserved':
                release_reservation(str(reservation.id))
            export.status = 'failed'
            export.error_message = str(exc)
            export.save(update_fields=['status', 'error_message'])
            mix.status = 'failed'
            mix.save(update_fields=['status'])
            if uploaded_key and not Song.objects.filter(audio_s3_key=uploaded_key).exists():
                try:
                    delete_file(uploaded_key)
                except Exception:
                    logger.exception('No se pudo limpiar el export fallido %s', export.id)
            return

        export.output_s3_key = s3_key
        export.status = 'ready'
        export.credits_used = 3
        export.save(update_fields=['output_s3_key', 'status', 'credits_used'])

        mix.duration_seconds = duration_seconds
        mix.output_s3_key = s3_key
        mix.status = 'ready'
        mix.save(update_fields=['duration_seconds', 'output_s3_key', 'status'])

        # Notificación interna y push cuando el mix esté listo.
        try:
            from apps.notifications.services import notify_user
            notify_user(
                user,
                type='mix_ready',
                reference_id=str(export.id),
                title='🎧 Tu mix está listo',
                message=f'La mezcla "{mix.title}" está lista para descargar.',
            )
        except Exception:
            logger.exception('No se pudo notificar el mix exportado %s', export.id)

    except Exception as exc:
        try:
            if uploaded_key and not Song.objects.filter(audio_s3_key=uploaded_key).exists():
                try:
                    delete_file(uploaded_key)
                except Exception:
                    logger.exception('No se pudo limpiar el export fallido %s', export_id)
            export = MixExport.objects.get(id=export_id)
            if self.request.retries >= self.max_retries:
                reservation = CreditReservation.objects.filter(
                    reference_id=export.id,
                    reference_type='mix_export',
                    status='reserved',
                ).first()
                if reservation:
                    release_reservation(str(reservation.id))
                export.status        = 'failed'
                export.error_message = str(exc)
                export.save(update_fields=['status', 'error_message'])
                export.mix_project.status = 'failed'
                export.mix_project.save(update_fields=['status'])
            else:
                MixExport.objects.filter(id=export.id, status='processing').update(
                    status='queued', error_message=str(exc)
                )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)
