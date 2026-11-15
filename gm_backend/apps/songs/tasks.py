import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def process_generation_job(self, job_id: str):
    from apps.songs.models import GenerationJob
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import (
        InsufficientCreditsError,
        confirm_reservation,
        deduct_credits,
        release_reservation,
    )
    from ml.modal_client import call_modal_endpoint, ModalGenerationError

    try:
        # La marca processing se adquiere dentro de una transacción corta.
        # No mantenemos el bloqueo mientras se espera a Modal.
        with transaction.atomic():
            # No usar select_related aquí: song es nullable y PostgreSQL no
            # permite FOR UPDATE sobre el lado nullable del OUTER JOIN.
            job = GenerationJob.objects.select_for_update().get(id=job_id)
            job.user  # carga la relación dentro de la transacción al usarla
            job.song  # idem; el bloqueo solo se mantiene sobre GenerationJob
            if job.status in {'completed', 'no_credits'}:
                return
            if job.status == 'processing':
                # La ejecución original sigue siendo la propietaria. Los
                # reintentos se reencolan como queued en el bloque de error.
                return
            song = job.song
            song.status = 'processing'
            song.save(update_fields=['status'])
            job.status = 'processing'
            job.started_at = timezone.now()
            job.save(update_fields=['status', 'started_at'])

        reservation = CreditReservation.objects.filter(
            user=job.user,
            reference_id=job.id,
            reference_type='generation_job',
        ).first()
        if reservation and reservation.status == 'released':
            job.status = 'no_credits'
            job.error_message = 'La reserva de créditos fue liberada.'
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'error_message', 'completed_at'])
            song.status = 'no_credits'
            song.save(update_fields=['status'])
            return

        # 2. Construir la llamada según el modo
        if job.remote_result:
            response = job.remote_result
        else:
            endpoint_url, body = _build_modal_request(song, job.mode)
            job.modal_endpoint_used = endpoint_url
            job.save(update_fields=['modal_endpoint_used'])

            # 3. Llamar a Modal. Se persiste inmediatamente la respuesta para
            # que un fallo posterior no provoque otra generación.
            response = call_modal_endpoint(endpoint_url, body)
            if not response.get('s3_key') or not response.get('cover_image_s3_key'):
                raise ValueError('Modal devolvió un resultado incompleto.')
            job.remote_result = response
            job.save(update_fields=['remote_result', 'updated_at'])

        # 4. Guardar resultado en la canción
        song.audio_s3_key = response['s3_key']
        song.thumbnail_s3_key = response['cover_image_s3_key']
        song.status = 'ready'

        # Guardar letra generada por IA (solo si el usuario no la proporcionó)
        if job.mode in ('from_description', 'with_described_lyrics'):
            generated_lyrics = response.get('lyrics', '')
            if generated_lyrics:
                song.lyrics = generated_lyrics
                song.lyrics_source = 'ai_generated'

        song.save(update_fields=['audio_s3_key', 'thumbnail_s3_key', 'status', 'lyrics', 'lyrics_source', 'updated_at'])

        # Calcular timestamps de letra en background (si hay letra y audio)
        if not song.instrumental and not song.lyrics_timestamps:
            compute_lyrics_timestamps.delay(str(song.id))

        # 5. Guardar tags/categorías generados por el LLM
        _save_categories(song, response.get('categories', []))

        # 6. Descontar crédito SOLO si fue exitoso
        try:
            if reservation and reservation.status == 'reserved':
                confirm_reservation(str(reservation.id))
            elif reservation and reservation.status == 'confirmed':
                pass
            elif job.credits_used == 0:
                deduct_credits(job.user, amount=1, reference_id=str(job.id), reference_type='generation_job')
        except InsufficientCreditsError as exc:
            reservation = CreditReservation.objects.filter(
                reference_id=job.id,
                reference_type='generation_job',
                status='reserved',
            ).first()
            if reservation:
                release_reservation(str(reservation.id))
            job.status = 'no_credits'
            job.error_message = str(exc)
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'error_message', 'completed_at'])
            song.status = 'no_credits'
            song.save(update_fields=['status'])
            return
        job.credits_used = 1
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save(update_fields=['credits_used', 'status', 'completed_at'])

        # 7. Notificación interna y push FCM
        try:
            from apps.notifications.services import notify_user
            notify_user(
                job.user,
                type='song_ready',
                reference_id=str(song.id),
                title='🎵 Tu canción está lista',
                message=f'"{song.title}" ya está en tu biblioteca.',
            )
        except Exception:
            logger.exception('No se pudo notificar la canción %s', song.id)

    except Exception as exc:
        try:
            job = GenerationJob.objects.get(id=job_id)
            if self.request.retries >= self.max_retries:
                reservation = CreditReservation.objects.filter(
                    reference_id=job.id,
                    reference_type='generation_job',
                    status='reserved',
                ).first()
                if reservation:
                    release_reservation(str(reservation.id))
                job.status = 'failed'
                job.error_message = str(exc)
                job.completed_at = timezone.now()
                job.save(update_fields=['status', 'error_message', 'completed_at'])
                job.song.status = 'failed'
                job.song.save(update_fields=['status'])
            else:
                GenerationJob.objects.filter(id=job.id, status='processing').update(
                    status='queued', error_message=str(exc)
                )
                job.song.status = 'queued'
                job.song.save(update_fields=['status'])
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


def _build_modal_request(song, mode: str):
    from django.conf import settings
    common = {
        'guidance_scale': song.guidance_scale,
        'infer_step': song.infer_step,
        'audio_duration': song.audio_duration,
        'seed': song.seed,
        'instrumental': song.instrumental,
        'vocal_type': song.vocal_type,
        'language': song.language,
    }
    if mode == 'from_description':
        return settings.MODAL_ENDPOINT_FROM_DESCRIPTION, {'full_described_song': song.description, **common}
    elif mode == 'with_lyrics':
        return settings.MODAL_ENDPOINT_WITH_LYRICS, {'prompt': song.prompt, 'lyrics': song.lyrics, **common}
    elif mode == 'with_described_lyrics':
        return settings.MODAL_ENDPOINT_FROM_DESCRIBED_LYRICS, {'prompt': song.prompt, 'described_lyrics': song.described_lyrics, **common}
    raise ValueError(f"Modo desconocido: {mode}")


def _save_categories(song, categories: list):
    from apps.songs.models import Tag, SongTag
    for cat_name in categories:
        tag, _ = Tag.objects.get_or_create(
            name=cat_name.strip().lower(),
            defaults={'category': 'genre'}
        )
        SongTag.objects.get_or_create(song=song, tag=tag)


@shared_task(bind=True, max_retries=1)
def compute_lyrics_timestamps(self, song_id: str):
    """Descarga el audio de una canción, corre Whisper y guarda los timestamps de letra."""
    import os
    import shutil
    import tempfile
    from django.db import connection
    from ml.storage_client import download_file

    # Verificar que ffmpeg está disponible
    if not shutil.which('ffmpeg'):
        return  # sin ffmpeg no podemos procesar

    try:
        from apps.songs.models import Song
        song = Song.objects.get(id=song_id, status='ready')
        if not song.audio_s3_key or song.instrumental:
            return

        fd, tmp_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

        try:
            download_file(song.audio_s3_key, tmp_path)

            lang = song.language if song.language in ('es', 'en') else None

            # Cerrar la conexión DB antes de la transcripción larga
            connection.close()

            import whisper
            model = whisper.load_model('base')
            result = model.transcribe(
                tmp_path,
                language=lang,
                task='transcribe',
                fp16=False,
                verbose=False,
                word_timestamps=True,
            )

            segments = result.get('segments', [])
            timestamps = [
                {'start': round(seg['start'], 2), 'end': round(seg['end'], 2), 'text': seg['text'].strip()}
                for seg in segments
                if seg.get('text', '').strip()
            ]

            if timestamps:
                Song.objects.filter(id=song_id).update(lyrics_timestamps=timestamps)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)
