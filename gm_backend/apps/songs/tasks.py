import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def _finalize_generation(job_id: str, response: dict) -> bool:
    """Publica canción, cobro y job dentro de una única transacción."""
    from django.db.models import Q, Sum
    from apps.credits.models import CreditReservation, CreditTransaction
    from apps.songs.models import GenerationJob, Song
    from apps.users.models import User

    snapshot = GenerationJob.objects.select_related('user').get(id=job_id)
    now = timezone.now()
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=snapshot.user_id)
        reservation = CreditReservation.objects.select_for_update().filter(
            user=user,
            reference_id=snapshot.id,
            reference_type='generation_job',
        ).first()
        job = GenerationJob.objects.select_for_update().get(id=job_id)
        song = Song.objects.select_for_update().get(id=job.song_id)

        if job.status == 'completed':
            return True
        if job.status in {'failed', 'no_credits'}:
            # A stale worker may return after recovery closed this job.
            return False
        if reservation and reservation.status == 'released':
            job.status = 'no_credits'
            job.error_message = 'La reserva de créditos fue liberada.'
            job.completed_at = now
            job.save(update_fields=['status', 'error_message', 'completed_at'])
            song.status = 'no_credits'
            song.save(update_fields=['status'])
            return False

        if reservation and reservation.status == 'reserved':
            if reservation.expires_at and reservation.expires_at <= now:
                reservation.status = 'released'
                reservation.save(update_fields=['status', 'updated_at'])
                job.status = 'no_credits'
                job.error_message = 'La reserva de créditos expiró.'
                job.completed_at = now
                job.save(update_fields=['status', 'error_message', 'completed_at'])
                song.status = 'no_credits'
                song.save(update_fields=['status'])
                return False
            if user.credit_balance < reservation.amount:
                reservation.status = 'released'
                reservation.save(update_fields=['status', 'updated_at'])
                job.status = 'no_credits'
                job.error_message = 'Sin créditos suficientes para confirmar.'
                job.completed_at = now
                job.save(update_fields=['status', 'error_message', 'completed_at'])
                song.status = 'no_credits'
                song.save(update_fields=['status'])
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
        elif not reservation and job.credits_used == 0:
            reserved = CreditReservation.objects.filter(
                user=user, status='reserved',
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).aggregate(
                total=Sum('amount')
            )['total'] or 0
            if user.credit_balance - reserved < 1:
                job.status = 'no_credits'
                job.error_message = 'Sin créditos suficientes.'
                job.completed_at = now
                job.save(update_fields=['status', 'error_message', 'completed_at'])
                song.status = 'no_credits'
                song.save(update_fields=['status'])
                return False
            user.credit_balance -= 1
            user.save(update_fields=['credit_balance'])
            CreditTransaction.objects.create(
                user=user,
                amount=-1,
                balance_after=user.credit_balance,
                type='generation_job',
                reference_id=job.id,
            )

        song.audio_s3_key = response['s3_key']
        song.thumbnail_s3_key = response['cover_image_s3_key']
        song.status = 'ready'
        if job.mode in ('from_description', 'with_described_lyrics'):
            generated_lyrics = response.get('lyrics', '')
            if generated_lyrics:
                song.lyrics = generated_lyrics
                song.lyrics_source = 'ai_generated'
        song.save(update_fields=[
            'audio_s3_key', 'thumbnail_s3_key', 'status', 'lyrics',
            'lyrics_source', 'updated_at',
        ])
        _save_categories(song, response.get('categories', []))
        job.credits_used = 1
        job.status = 'completed'
        job.completed_at = now
        job.save(update_fields=['credits_used', 'status', 'completed_at'])
        return True


GENERATION_POLL_INTERVAL_SECONDS = 5


def _schedule_generation_poll(job_id: str, countdown: int = GENERATION_POLL_INTERVAL_SECONDS):
    poll_generation_job.apply_async(args=[job_id], countdown=countdown)


def _set_locked_song_status(song_id, status: str):
    """Bloquea y actualiza la canción del job (puede no existir: song es nullable)."""
    from apps.songs.models import Song

    if not song_id:
        return
    song = Song.objects.select_for_update().filter(id=song_id).first()
    if song:
        song.status = status
        song.save(update_fields=['status'])


def _mark_generation_failed(job_id: str, message: str):
    from apps.credits.models import CreditReservation
    from apps.songs.models import GenerationJob
    from apps.users.models import User

    user_id = GenerationJob.objects.filter(id=job_id).values_list('user_id', flat=True).first()
    failed_job = None
    with transaction.atomic():
        # El usuario se bloquea primero, como en _finalize_generation y en la
        # recuperación de core: así esas transacciones se serializan sin deadlock.
        if user_id:
            User.objects.select_for_update().filter(pk=user_id).first()
        reservation = CreditReservation.objects.select_for_update().filter(
            reference_id=job_id,
            reference_type='generation_job',
            status='reserved',
        ).first()
        job = GenerationJob.objects.select_for_update().get(id=job_id)
        if job.status not in {'queued', 'processing'}:
            return
        if reservation:
            # Ya tenemos la reserva bloqueada dentro de esta transacción.
            # Evita abrir otra transacción y cambiar el orden de locks.
            reservation.status = 'released'
            reservation.save(update_fields=['status', 'updated_at'])
        job.status = 'failed'
        job.error_message = message
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
        _set_locked_song_status(job.song_id, 'failed')
        failed_job = job

    if failed_job:
        try:
            from apps.notifications.services import notify_user

            song_title = failed_job.song.title if failed_job.song else 'tu canción'
            notify_user(
                failed_job.user,
                type='song_failed',
                reference_id=str(failed_job.id),
                title='No se pudo generar la canción',
                message=f'Falló la generación de "{song_title}": {message[:900]}',
                push_message='La generación de tu canción no pudo completarse.',
            )
        except Exception:
            logger.exception('No se pudo notificar la generación fallida %s', job_id)


def _mark_generation_no_credits(job_id: str, message: str):
    from apps.songs.models import GenerationJob

    with transaction.atomic():
        job = GenerationJob.objects.select_for_update().get(id=job_id)
        if job.status not in {'queued', 'processing'}:
            return
        job.status = 'no_credits'
        job.error_message = message
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at'])
        _set_locked_song_status(job.song_id, 'no_credits')


def _complete_generation(job_id: str, response: dict):
    from apps.songs.models import GenerationJob

    if not response.get('s3_key') or not response.get('cover_image_s3_key'):
        raise ValueError('Modal devolvió un resultado incompleto.')
    job = GenerationJob.objects.select_related('song', 'user').get(id=job_id)
    job.remote_result = response
    job.save(update_fields=['remote_result', 'updated_at'])
    finalized = _finalize_generation(job_id, response)
    if not finalized:
        return
    if not job.song.instrumental and not job.song.lyrics_timestamps:
        compute_lyrics_timestamps.delay(str(job.song.id))
    try:
        from apps.notifications.services import notify_user
        notify_user(
            job.user,
            type='song_ready',
            reference_id=str(job.song.id),
            title='🎵 Tu canción está lista',
            message=f'"{job.song.title}" ya está en tu biblioteca.',
        )
    except Exception:
        logger.exception('No se pudo notificar la canción %s', job.song.id)


@shared_task(bind=True, max_retries=2)
def process_generation_job(self, job_id: str):
    from apps.credits.models import CreditReservation
    from apps.songs.models import GenerationJob
    from ml.modal_client import submit_music_job

    try:
        with transaction.atomic():
            # of=('self',): song es nullable (LEFT JOIN) y PostgreSQL no permite
            # FOR UPDATE sobre el lado nullable; la canción se bloquea aparte.
            job = GenerationJob.objects.select_for_update(of=('self',)).select_related(
                'song'
            ).get(id=job_id)
            if job.status in {'completed', 'no_credits'}:
                return
            if job.remote_result:
                response = job.remote_result
            elif job.remote_job_id:
                _schedule_generation_poll(job_id, countdown=0)
                return
            else:
                _set_locked_song_status(job.song_id, 'processing')
                job.status = 'processing'
                job.started_at = timezone.now()
                job.error_message = None
                job.save(update_fields=['status', 'started_at', 'error_message'])
                response = None

        reservation = CreditReservation.objects.filter(
            user=job.user,
            reference_id=job.id,
            reference_type='generation_job',
        ).first()
        if reservation and reservation.status == 'released':
            _mark_generation_no_credits(job_id, 'La reserva de créditos fue liberada.')
            return

        if response:
            _complete_generation(job_id, response)
            return

        endpoint_url, body = _build_modal_request(job.song, job.mode, str(job.id))
        job.modal_endpoint_used = endpoint_url
        job.save(update_fields=['modal_endpoint_used'])
        remote = submit_music_job(endpoint_url, body)
        job.remote_job_id = remote['remote_job_id']
        job.status = 'queued'
        job.started_at = timezone.now()
        job.save(update_fields=['remote_job_id', 'status', 'started_at', 'updated_at'])
        _schedule_generation_poll(job_id, countdown=0)
    except Exception as exc:
        try:
            job = GenerationJob.objects.select_related('song').get(id=job_id)
            if self.request.retries >= self.max_retries:
                _mark_generation_failed(job_id, str(exc))
            else:
                GenerationJob.objects.filter(id=job.id, status='processing').update(
                    status='queued', error_message=str(exc)
                )
                job.song.status = 'queued'
                job.song.save(update_fields=['status'])
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=5)
def poll_generation_job(self, job_id: str):
    from django.conf import settings
    from apps.songs.models import GenerationJob
    from ml.modal_client import get_music_job_status

    try:
        job = GenerationJob.objects.select_related('song').get(id=job_id)
        if job.status in {'completed', 'failed', 'no_credits'}:
            return
        if not job.remote_job_id:
            if job.remote_result:
                _complete_generation(job_id, job.remote_result)
            else:
                _mark_generation_failed(job_id, 'El job no tiene identificador remoto.')
            return
        if job.started_at and (
            timezone.now() - job.started_at
        ).total_seconds() > getattr(settings, 'GENERATION_PROCESSING_STALE_SECONDS', 1800):
            _mark_generation_failed(job_id, 'La generación excedió el tiempo máximo permitido.')
            return

        remote = get_music_job_status(
            job.modal_endpoint_used,
            job.remote_job_id,
        )
        remote_status = remote.get('status')
        if remote_status in {'queued', 'processing'}:
            GenerationJob.objects.filter(id=job_id).update(status=remote_status)
            job.song.status = remote_status
            job.song.save(update_fields=['status'])
            _schedule_generation_poll(job_id)
            return
        if remote_status == 'failed':
            _mark_generation_failed(
                job_id,
                remote.get('error_message') or 'Modal no pudo generar la canción.',
            )
            return
        if remote_status != 'completed':
            _mark_generation_failed(job_id, f'Estado remoto desconocido: {remote_status}')
            return
        _complete_generation(job_id, remote)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=GENERATION_POLL_INTERVAL_SECONDS)
        _mark_generation_failed(job_id, str(exc))


def _build_modal_request(song, mode: str, client_job_id: str | None = None):
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
        endpoint = settings.MODAL_ENDPOINT_FROM_DESCRIPTION
        body = {'full_described_song': song.description, **common}
    elif mode == 'with_lyrics':
        endpoint = settings.MODAL_ENDPOINT_WITH_LYRICS
        body = {'prompt': song.prompt, 'lyrics': song.lyrics, **common}
    elif mode == 'with_described_lyrics':
        endpoint = settings.MODAL_ENDPOINT_FROM_DESCRIBED_LYRICS
        body = {'prompt': song.prompt, 'described_lyrics': song.described_lyrics, **common}
    else:
        raise ValueError(f"Modo desconocido: {mode}")
    if client_job_id:
        body['client_job_id'] = client_job_id
    return endpoint, body


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
