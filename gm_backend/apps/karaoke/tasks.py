import logging
import os
import shutil
import tempfile
from contextlib import contextmanager

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ml.storage_client import download_file

logger = logging.getLogger(__name__)


def _save_processing_stage(track, stage: str, *, status: str = 'processing') -> None:
    """Persist a real processing stage and refresh the recovery heartbeat."""
    track.status = status
    track.processing_stage = stage
    track.save(update_fields=['status', 'processing_stage', 'updated_at'])


@contextmanager
def _processing_heartbeat(track_id: str, stage: str):
    """Scope for long work; stage boundaries refresh the recovery timestamp."""
    yield


def _synchronize_timestamps(timestamps: list[dict]) -> list[dict]:
    """Validate and normalize Whisper timestamps without reprocessing audio."""
    synchronized = []
    previous_end = 0.0
    for item in timestamps:
        try:
            start = max(0.0, float(item['start']))
            end = max(start, float(item['end']))
        except (KeyError, TypeError, ValueError):
            continue
        if end <= start or start < previous_end:
            start = max(start, previous_end)
            if end <= start:
                continue
        text = str(item.get('text', '')).strip()
        if not text:
            continue
        synchronized.append({
            'start': round(start, 2),
            'end': round(end, 2),
            'text': text,
        })
        previous_end = end
    return synchronized


def _release_pending_access(access_id: str) -> None:
    """Libera una reserva y elimina un acceso que no pudo cobrarse."""
    from django.db import transaction

    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import release_reservation
    from apps.karaoke.models import UserKaraokeAccess

    try:
        with transaction.atomic():
            access = UserKaraokeAccess.objects.select_for_update().get(id=access_id)
            reservation = CreditReservation.objects.filter(
                user_id=access.user_id,
                reference_id=access.karaoke_track_id,
                reference_type='karaoke_access',
            ).first()
            if reservation and reservation.status == 'confirmed':
                access.credits_paid = 2
                access.save(update_fields=['credits_paid'])
                return
            if reservation and reservation.status == 'reserved':
                release_reservation(str(reservation.id))
            access.delete()
    except UserKaraokeAccess.DoesNotExist:
        pass


def _charge_pending_accesses(karaoke_track_id: str) -> None:
    """Cobra una sola vez los accesos pendientes tras un karaoke exitoso."""
    from django.db import transaction

    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import (
        check_balance,
        confirm_reservation,
        deduct_credits,
    )
    from apps.karaoke.models import UserKaraokeAccess
    from apps.users.models import User

    pending_accesses = UserKaraokeAccess.objects.filter(
        karaoke_track_id=karaoke_track_id,
        credits_paid=0,
    ).values_list('id', flat=True)

    for access_id in pending_accesses:
        try:
            with transaction.atomic():
                access = (
                    UserKaraokeAccess.objects
                    .select_for_update()
                    .select_related('user')
                    .get(id=access_id)
                )
                if access.credits_paid != 0:
                    continue

                user = User.objects.select_for_update().get(pk=access.user_id)
                reservation = CreditReservation.objects.filter(
                    user=user,
                    reference_id=access.karaoke_track_id,
                    reference_type='karaoke_access',
                ).first()
                if reservation and reservation.status == 'confirmed':
                    # The credit transaction already exists; only finalize access.
                    pass
                elif reservation and reservation.status == 'reserved':
                    try:
                        confirm_reservation(str(reservation.id))
                    except ValueError:
                        access.delete()
                        logger.info(
                            'Acceso pendiente eliminado porque su reserva expiró: acceso=%s',
                            access_id,
                        )
                        continue
                elif reservation and reservation.status == 'released':
                    access.delete()
                    logger.info(
                        'Acceso pendiente eliminado porque su reserva fue liberada: acceso=%s',
                        access_id,
                    )
                    continue
                elif not check_balance(user, required=2):
                    access.delete()
                    logger.warning(
                        'Acceso pendiente eliminado por saldo insuficiente: usuario=%s karaoke=%s',
                        user.pk,
                        karaoke_track_id,
                    )
                    continue
                else:
                    deduct_credits(user, amount=2, reference_id=karaoke_track_id, reference_type='karaoke')
                access.credits_paid = 2
                access.save(update_fields=['credits_paid'])
        except UserKaraokeAccess.DoesNotExist:
            continue
        except Exception:
            logger.exception(
                'No se pudo cobrar el acceso pendiente: acceso=%s karaoke=%s',
                access_id,
                karaoke_track_id,
            )
            _release_pending_access(str(access_id))


def _release_pending_accesses(karaoke_track_id: str) -> None:
    """Libera todos los accesos aún no cobrados cuando falla la generación."""
    from apps.karaoke.models import UserKaraokeAccess

    pending_ids = UserKaraokeAccess.objects.filter(
        karaoke_track_id=karaoke_track_id,
        credits_paid=0,
    ).values_list('id', flat=True)
    for access_id in pending_ids:
        _release_pending_access(str(access_id))


@shared_task(bind=True, max_retries=2)
def generate_karaoke_track(self, karaoke_track_id: str):
    return _run_karaoke_step(self, karaoke_track_id, allow_submit=True)


@shared_task(bind=True, max_retries=3)
def poll_karaoke_track(self, karaoke_track_id: str):
    """Consulta una vez el trabajo remoto y reencola el siguiente polling."""
    return _run_karaoke_step(self, karaoke_track_id, allow_submit=False)


def _run_karaoke_step(self, karaoke_track_id: str, *, allow_submit: bool):
    from apps.karaoke.models import KaraokeTrack
    from ml.modal_client import get_stem_job_status, submit_stem_job

    try:
        track = KaraokeTrack.objects.select_related('song').get(id=karaoke_track_id)
        song = track.song

        if track.status in {'ready', 'failed'}:
            return
        track.status = 'processing'
        track.error_message = None
        track.save(update_fields=['status', 'error_message', 'updated_at'])

        # 1. Separar stems con Demucs vía Modal. El client_job_id estable
        # permite reanudar después de un timeout sin duplicar procesamiento.
        if not track.remote_job_id:
            if not allow_submit:
                raise RuntimeError('El trabajo de karaoke no tiene identificador remoto.')
            _save_processing_stage(track, 'separating')
            response = submit_stem_job(
                settings.MODAL_ENDPOINT_SEPARATE_STEMS,
                {'s3_key': song.audio_s3_key, 'client_job_id': str(track.id)},
            )
            track.remote_job_id = response['remote_job_id']
            track.save(update_fields=['remote_job_id'])
            poll_karaoke_track.apply_async(args=[karaoke_track_id], countdown=0)
            return

        if not track.vocals_s3_key or not track.instrumental_s3_key:
            _save_processing_stage(track, 'separating')
        if not track.vocals_s3_key or not track.instrumental_s3_key:
            if (
                timezone.now() - track.created_at
            ).total_seconds() > settings.STEM_REMOTE_TIMEOUT_SECONDS:
                raise TimeoutError('La separación de karaoke excedió el tiempo máximo permitido.')

            remote = get_stem_job_status(
                settings.MODAL_ENDPOINT_SEPARATE_STEMS,
                track.remote_job_id,
            )
            remote_status = remote.get('status')
            if remote_status in {'queued', 'processing'}:
                track.status = remote_status
                track.processing_stage = 'separating'
                track.save(update_fields=['status', 'processing_stage', 'updated_at'])
                poll_karaoke_track.apply_async(
                    args=[karaoke_track_id],
                    countdown=settings.STEM_POLL_INTERVAL_SECONDS,
                )
                return
            if remote_status == 'failed':
                raise RuntimeError(remote.get('error_message') or 'Demucs no pudo separar el audio.')
            if remote_status != 'completed':
                raise RuntimeError(f'Estado remoto desconocido: {remote_status}')
            stems = remote.get('stems') or {}
            if not stems.get('vocals') or not stems.get('no_vocals'):
                raise RuntimeError('Demucs no devolvió ambos stems requeridos.')

            track.instrumental_s3_key = stems.get('no_vocals')
            track.vocals_s3_key = stems.get('vocals')
            track.save(update_fields=[
                'instrumental_s3_key', 'vocals_s3_key', 'updated_at',
            ])

        # 2. Whisper sobre el stem vocal (requiere ffmpeg disponible)
        _save_processing_stage(track, 'transcribing')
        ffmpeg_path = settings.FFMPEG_PATH
        ffmpeg_exists = os.path.exists(ffmpeg_path) or shutil.which(ffmpeg_path)
        if not ffmpeg_exists:
            logger.warning(f'ffmpeg no encontrado en {ffmpeg_path} — Whisper saltado, lyrics_timestamps quedará null')
        if track.vocals_s3_key and ffmpeg_exists and track.lyrics_timestamps is None:
            with _processing_heartbeat(karaoke_track_id, 'transcribing'):
                fd, tmp_path = tempfile.mkstemp(suffix='.wav')
                os.close(fd)
                try:
                    download_file(track.vocals_s3_key, tmp_path)

                    # Añadir carpeta de ffmpeg al PATH para que Whisper la encuentre
                    ffmpeg_dir = os.path.dirname(os.path.abspath(ffmpeg_path))
                    os.environ['PATH'] = (
                        f"{ffmpeg_dir}{os.pathsep}{os.environ.get('PATH', '')}"
                    )

                    import whisper
                    model = whisper.load_model('base')
                    language = song.language if song.language in ('es', 'en') else None
                    result = model.transcribe(
                        tmp_path,
                        language=language,
                        task='transcribe',
                        fp16=False,
                        word_timestamps=True,
                    )
                    segments = result.get('segments', [])
                    timestamps = [
                        {
                            'start': round(s['start'], 2),
                            'end': round(s['end'], 2),
                            'text': s['text'].strip(),
                        }
                        for s in segments if s.get('text', '').strip()
                    ]

                    # Limpiar lyrics con Gemini si está disponible
                    if settings.GEMINI_API_KEY and timestamps:
                        whisper_text = '\n'.join(t['text'] for t in timestamps)
                        reference_lyrics = song.lyrics or song.described_lyrics or song.prompt or ''

                        num_lines = len(timestamps)

                        prompt = f"""Eres un experto ingeniero de audio preparando subtítulos para karaoke.
CONTEXTO CRÍTICO:
1. El audio original fue generado por IA, por lo que contiene artefactos sonoros, voces distorsionadas y balbuceos. Whisper intentó transcribir estos ruidos como palabras inventadas o sin sentido.
2. La LETRA DE REFERENCIA suele estar INCOMPLETA. Muchas veces la canción repite estrofas, coros, o hace "ad-libs" al final que no están escritos en la referencia.

TU MISIÓN:
Dada la transcripción fonética (Whisper) y la letra de referencia, limpia el texto línea por línea.

REGLAS ESTRICTAS:
1. ARREGLA LOS BALBUCEOS: Si Whisper detectó palabras raras, busca la frase más parecida en la referencia y corrígela.
2. EXTRAPOLA CON LÓGICA: Si la canción repite una parte o sigue cantando después de que se acaba la letra de referencia, usa tu sentido común. Transforma los intentos raros de Whisper en palabras reales que tengan sentido con el resto de la canción. NO dejes palabras inventadas.
3. MANTÉN LA ESTRUCTURA: Te enviaré {num_lines} líneas. DEBES devolver EXACTAMENTE {num_lines} líneas. No unas ni separes las frases.
4. FORMATO: Devuelve solo las líneas corregidas, una por línea, en texto plano (sin markdown, ni números).

LETRA DE REFERENCIA:
{reference_lyrics[:800]}

TRANSCRIPCIÓN DE WHISPER (Con errores de IA, {num_lines} líneas):
{whisper_text}

LÍNEAS CORREGIDAS:"""

                        try:
                            from google import genai
                            client = genai.Client(api_key=settings.GEMINI_API_KEY)
                            response = client.models.generate_content(
                                model=settings.GEMINI_MODEL,
                                contents=prompt,
                            )
                            cleaned_text = (response.text or '').strip()
                            cleaned_lines = [
                                line.strip() for line in cleaned_text.split('\n') if line.strip()
                            ]
                            # Si Gemini falla o cambia la cardinalidad, Whisper sigue siendo
                            # el resultado válido y no se reemplaza parcialmente.
                            if len(cleaned_lines) == num_lines:
                                for timestamp, cleaned_line in zip(timestamps, cleaned_lines):
                                    timestamp['text'] = cleaned_line
                            else:
                                logger.warning(
                                    'Gemini devolvió %s líneas; se conserva Whisper (%s).',
                                    len(cleaned_lines), num_lines,
                                )
                        except Exception:
                            logger.exception('Gemini falló; se conserva la transcripción de Whisper.')

                    track.lyrics_timestamps = timestamps
                    track.lyrics = '\n'.join(t['text'] for t in timestamps)
                    track.save(update_fields=['lyrics', 'lyrics_timestamps', 'updated_at'])
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

        _save_processing_stage(track, 'synchronizing')
        with _processing_heartbeat(karaoke_track_id, 'synchronizing'):
            synchronized = _synchronize_timestamps(track.lyrics_timestamps or [])
            track.lyrics_timestamps = synchronized
            track.lyrics = '\n'.join(item['text'] for item in synchronized)
            track.save(update_fields=['lyrics', 'lyrics_timestamps', 'updated_at'])

        _charge_pending_accesses(karaoke_track_id)

        # Recovery may have closed this track while Whisper was running.
        # Re-read before publishing the remote result.
        if not KaraokeTrack.objects.filter(
            id=karaoke_track_id,
            status__in=['queued', 'processing'],
        ).exists():
            return

        track.status = 'ready'
        track.processing_stage = 'completed'
        track.processed_at = timezone.now()
        track.save(update_fields=[
            'status', 'processing_stage', 'processed_at', 'lyrics',
            'lyrics_timestamps', 'updated_at',
        ])

        try:
            from apps.notifications.services import notify_user

            for access in track.user_accesses.select_related('user').all():
                try:
                    notify_user(access.user, type='karaoke_ready', reference_id=str(track.id))
                except Exception:
                    logger.exception(
                        'No se pudo notificar al usuario %s sobre el karaoke %s',
                        access.user_id,
                        track.id,
                    )
        except Exception:
            logger.exception('No se pudo notificar el karaoke listo %s', track.id)

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            try:
                _release_pending_accesses(karaoke_track_id)
                KaraokeTrack.objects.filter(id=karaoke_track_id).update(
                    status='failed',
                    processing_stage='failed',
                    error_message=str(exc)[:500],
                    updated_at=timezone.now(),
                )
            except Exception:
                pass
        else:
            KaraokeTrack.objects.filter(id=karaoke_track_id).update(
                status='processing',
                error_message=str(exc)[:500],
                updated_at=timezone.now(),
            )
        raise self.retry(exc=exc, countdown=60)
