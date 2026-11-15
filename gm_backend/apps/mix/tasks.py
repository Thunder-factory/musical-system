import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
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
            # La canción permanece no publicada hasta que el cobro y el
            # estado de la exportación se confirmen.
            status='draft',
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


def _finalize_mix_export(export_id, song_id, s3_key, duration_seconds):
    """Confirma el cobro y publica todos los registros en una transacción."""
    from django.db.models import Q, Sum
    from apps.credits.models import CreditReservation, CreditTransaction
    from apps.mix.models import MixExport, MixProject
    from apps.songs.models import Song
    from apps.users.models import User

    with transaction.atomic():
        export_snapshot = MixExport.objects.select_related('mix_project').get(pk=export_id)
        user = User.objects.select_for_update().get(pk=export_snapshot.mix_project.user_id)
        reservation = CreditReservation.objects.select_for_update().filter(
            user=user,
            reference_id=export_snapshot.id,
            reference_type='mix_export',
        ).first()
        export = MixExport.objects.select_for_update().get(pk=export_id)
        mix = MixProject.objects.select_for_update().get(pk=export.mix_project_id)
        song = Song.objects.select_for_update().get(pk=song_id)
        now = timezone.now()

        if export.status == 'ready' and export.output_s3_key:
            return True
        if export.status == 'failed':
            # Do not let an old renderer publish after recovery closed it.
            return False
        if reservation and reservation.status == 'released':
            export.status = 'failed'
            export.error_message = 'La reserva de créditos del mix fue liberada.'
            export.save(update_fields=['status', 'error_message'])
            mix.status = 'failed'
            mix.save(update_fields=['status'])
            return False

        if reservation and reservation.status == 'reserved':
            if reservation.expires_at and reservation.expires_at <= now:
                reservation.status = 'released'
                reservation.save(update_fields=['status', 'updated_at'])
                export.status = 'failed'
                export.error_message = 'La reserva de créditos del mix expiró.'
                export.save(update_fields=['status', 'error_message'])
                mix.status = 'failed'
                mix.save(update_fields=['status'])
                return False
            if user.credit_balance < reservation.amount:
                reservation.status = 'released'
                reservation.save(update_fields=['status', 'updated_at'])
                export.status = 'failed'
                export.error_message = 'Sin créditos suficientes para confirmar.'
                export.save(update_fields=['status', 'error_message'])
                mix.status = 'failed'
                mix.save(update_fields=['status'])
                return False
            user.credit_balance -= reservation.amount
            user.save(update_fields=['credit_balance'])
            CreditTransaction.objects.create(
                user=user,
                amount=-reservation.amount,
                balance_after=user.credit_balance,
                type=reservation.reference_type,
                reference_id=reservation.reference_id,
            )
            reservation.status = 'confirmed'
            reservation.save(update_fields=['status', 'updated_at'])
        elif not reservation and export.credits_used == 0:
            reserved = CreditReservation.objects.filter(
                user=user, status='reserved',
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).aggregate(
                total=Sum('amount')
            )['total'] or 0
            if user.credit_balance - reserved < 3:
                export.status = 'failed'
                export.error_message = 'Sin créditos suficientes.'
                export.save(update_fields=['status', 'error_message'])
                mix.status = 'failed'
                mix.save(update_fields=['status'])
                return False
            user.credit_balance -= 3
            user.save(update_fields=['credit_balance'])
            CreditTransaction.objects.create(
                user=user,
                amount=-3,
                balance_after=user.credit_balance,
                type='mix_export',
                reference_id=export.id,
            )

        song.status = 'ready'
        song.save(update_fields=['status', 'updated_at'])
        export.output_s3_key = s3_key
        export.status = 'ready'
        export.credits_used = 3
        export.save(update_fields=['output_s3_key', 'status', 'credits_used'])
        mix.duration_seconds = duration_seconds
        mix.output_s3_key = s3_key
        mix.status = 'ready'
        mix.save(update_fields=['duration_seconds', 'output_s3_key', 'status'])
        return True


def _discard_provisional_mix_song(song_id, s3_key, delete_file):
    """Elimina solo una canción draft creada por esta exportación."""
    from apps.songs.models import Song

    deleted = False
    with transaction.atomic():
        song = Song.objects.select_for_update().filter(
            pk=song_id,
            audio_s3_key=s3_key,
            status='draft',
        ).first()
        if song:
            song.delete()
            deleted = True

    if deleted and not Song.objects.filter(audio_s3_key=s3_key).exists():
        try:
            delete_file(s3_key)
        except Exception:
            logger.exception('No se pudo eliminar el archivo provisional %s', s3_key)

ffmpeg_path = config('FFMPEG_PATH', default=None)
if ffmpeg_path:
    pydub.AudioSegment.converter = ffmpeg_path


@shared_task(bind=True, max_retries=2)
def render_mix(
    self,
    export_id: str,
    tag_ids: list = None,
    muted_clip_ids: list = None,
    solo_clip_ids: list = None,
):
    from apps.mix.models import MixExport, MixClip
    from apps.mix.services.audio_editor import (
        apply_clip_effects, compose_timeline, download_audio_from_storage,
        get_clip_storage_key,
    )
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import check_balance, release_reservation
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
            if export.status == 'processing' and export.updated_at > (
                timezone.now() - timedelta(
                    seconds=getattr(settings, 'MIX_EXPORT_PROCESSING_STALE_SECONDS', 1800)
                )
            ):
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

        persisted_muted_ids = {
            str(clip_id) for clip_id in clips.filter(is_muted=True).values_list('id', flat=True)
        }
        persisted_solo_ids = {
            str(clip_id) for clip_id in clips.filter(is_solo=True).values_list('id', flat=True)
        }
        muted_ids = (
            {str(clip_id) for clip_id in muted_clip_ids}
            if muted_clip_ids is not None
            else persisted_muted_ids
        )
        solo_ids = (
            {str(clip_id) for clip_id in solo_clip_ids}
            if solo_clip_ids is not None
            else persisted_solo_ids
        )
        if solo_ids:
            clips = clips.filter(id__in=solo_ids)
        if muted_ids:
            clips = clips.exclude(id__in=muted_ids)
        if not clips.exists():
            raise ValueError('No hay clips audibles para exportar.')

        processed_clips = []
        for clip in clips:
            object_key = get_clip_storage_key(clip)
            audio_path = download_audio_from_storage(object_key)
            try:
                audio     = AudioSegment.from_file(audio_path)
                processed = apply_clip_effects(audio, clip)
                processed_clips.append((clip, processed))
            finally:
                os.unlink(audio_path)
            # Heartbeat so Beat does not reclaim a valid long export.
            MixExport.objects.filter(id=export_id, status='processing').update(
                error_message=None,
                updated_at=timezone.now(),
            )

        final_audio = compose_timeline(processed_clips)

        output_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=f'.{export.format}', delete=False) as tmp:
                bitrate = export.quality if export.format == 'mp3' else None
                output_path = tmp.name
            final_audio.export(output_path, format=export.format, bitrate=bitrate)

            s3_key = f"mix-exports/{mix.id}/{export.id}.{export.format}"
            upload_file(output_path, s3_key)
            uploaded_key = s3_key
            MixExport.objects.filter(id=export_id, status='processing').update(
                updated_at=timezone.now(),
            )
        finally:
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)

        duration_seconds = len(final_audio) // 1000

        mix_song = _ensure_mix_song(mix, user, s3_key, duration_seconds, tag_ids, clips)

        finalized = _finalize_mix_export(
            export.id, mix_song.id, s3_key, duration_seconds,
        )
        if not finalized:
            _discard_provisional_mix_song(mix_song.id, s3_key, delete_file)
            uploaded_key = None
            return

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
