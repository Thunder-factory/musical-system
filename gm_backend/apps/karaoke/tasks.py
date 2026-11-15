import logging
import os
import shutil
import tempfile
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ml.storage_client import download_file

logger = logging.getLogger(__name__)


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


@shared_task(bind=True, max_retries=2)
def generate_karaoke_track(self, karaoke_track_id: str):
    from apps.karaoke.models import KaraokeTrack
    from ml.modal_client import get_stem_job_status, submit_stem_job

    try:
        track = KaraokeTrack.objects.select_related('song').get(id=karaoke_track_id)
        song = track.song

        track.status = 'processing'
        track.save(update_fields=['status'])

        # 1. Separar stems con Demucs vía Modal. El client_job_id estable
        # permite reanudar después de un timeout sin duplicar procesamiento.
        if not track.remote_job_id:
            response = submit_stem_job(
                settings.MODAL_ENDPOINT_SEPARATE_STEMS,
                {'s3_key': song.audio_s3_key, 'client_job_id': str(track.id)},
            )
            track.remote_job_id = response['remote_job_id']
            track.save(update_fields=['remote_job_id'])

        deadline = time.monotonic() + settings.STEM_REMOTE_TIMEOUT_SECONDS
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError('La separación de karaoke excedió el tiempo máximo permitido.')
            remote = get_stem_job_status(
                settings.MODAL_ENDPOINT_SEPARATE_STEMS,
                track.remote_job_id,
            )
            remote_status = remote.get('status')
            if remote_status in {'queued', 'processing'}:
                track.status = remote_status
                track.save(update_fields=['status'])
                time.sleep(settings.STEM_POLL_INTERVAL_SECONDS)
                continue
            if remote_status == 'failed':
                raise RuntimeError(remote.get('error_message') or 'Demucs no pudo separar el audio.')
            if remote_status != 'completed':
                raise RuntimeError(f'Estado remoto desconocido: {remote_status}')
            stems = remote.get('stems') or {}
            if not stems.get('vocals') or not stems.get('no_vocals'):
                raise RuntimeError('Demucs no devolvió ambos stems requeridos.')
            break

        track.instrumental_s3_key = stems.get('no_vocals')
        track.vocals_s3_key       = stems.get('vocals')
        track.save(update_fields=['instrumental_s3_key', 'vocals_s3_key'])

        # 2. Whisper sobre el stem vocal (requiere ffmpeg disponible)
        ffmpeg_path = settings.FFMPEG_PATH
        ffmpeg_exists = os.path.exists(ffmpeg_path) or shutil.which(ffmpeg_path)
        if not ffmpeg_exists:
            logger.warning(f'ffmpeg no encontrado en {ffmpeg_path} — Whisper saltado, lyrics_timestamps quedará null')
        if track.vocals_s3_key and ffmpeg_exists:
            fd, tmp_path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            try:
                download_file(track.vocals_s3_key, tmp_path)

                # Cerrar conexión DB antes de Whisper (proceso largo, evita timeout)
                from django.db import connection
                connection.close()

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
                        'end':   round(s['end'],   2),
                        'text':  s['text'].strip(),
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
                            model='gemini-2.5-flash',
                            contents=prompt
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
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        track.status       = 'ready'
        track.processed_at = timezone.now()
        track.save(update_fields=['status', 'processed_at', 'lyrics', 'lyrics_timestamps'])

        _charge_pending_accesses(karaoke_track_id)

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            try:
                KaraokeTrack.objects.filter(id=karaoke_track_id).update(
                    status='failed',
                    error_message=str(exc)[:500],
                )
            except Exception:
                pass
        else:
            KaraokeTrack.objects.filter(id=karaoke_track_id).update(
                status='processing',
                error_message=str(exc)[:500],
            )
        raise self.retry(exc=exc, countdown=60)
