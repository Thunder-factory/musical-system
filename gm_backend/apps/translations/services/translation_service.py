"""Reglas de negocio para crear trabajos de traducción (doblaje) de videos musicales."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.credits.services.credit_service import (
    InsufficientCreditsError,
    release_reservation,
    reserve_credits,
)
from apps.translations.models import TranslationJob
from ml.storage_client import delete_file, upload_fileobj

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from apps.users.models import User

__all__ = [
    'ALLOWED_VIDEO_EXTENSIONS',
    'InsufficientCreditsError',
    'SUPPORTED_LANGUAGES',
    'TranslationValidationError',
    'get_translation_config',
    'request_translation',
    'validate_video_file',
]

ALLOWED_VIDEO_EXTENSIONS = ('.mp4', '.mov', '.webm')
SUPPORTED_LANGUAGES = dict(TranslationJob.LANGUAGE_CHOICES)
RESERVATION_TYPE = 'translation_job'
MAX_TEXT_FIELD_LENGTH = 200


class TranslationValidationError(Exception):
    """Los datos enviados (video, idioma o metadatos) no son válidos."""


def get_translation_config() -> dict:
    """Límites públicos que el frontend usa para validar antes de subir."""
    return {
        'languages': [
            {'code': code, 'label': label}
            for code, label in TranslationJob.LANGUAGE_CHOICES
        ],
        'allowed_extensions': list(ALLOWED_VIDEO_EXTENSIONS),
        'max_duration_seconds': settings.TRANSLATION_MAX_DURATION_SECONDS,
        'max_file_size_mb': settings.TRANSLATION_MAX_FILE_SIZE_MB,
        'credit_cost': settings.TRANSLATION_CREDIT_COST,
    }


def _clean_text(value: str | None, field: str) -> str:
    text = (value or '').strip()
    if len(text) > MAX_TEXT_FIELD_LENGTH:
        raise TranslationValidationError(
            f'El campo {field} admite como máximo {MAX_TEXT_FIELD_LENGTH} caracteres.'
        )
    return text


def validate_video_file(file: UploadedFile, filename: str) -> tuple[str, float]:
    """Valida extensión, tamaño, duración y pista de audio. Devuelve (sha256, duración)."""
    extension = os.path.splitext(filename or '')[1].lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise TranslationValidationError('Solo se aceptan videos MP4, MOV o WebM.')

    size = getattr(file, 'size', 0) or 0
    if size <= 0:
        raise TranslationValidationError('El video está vacío.')
    max_bytes = settings.TRANSLATION_MAX_FILE_SIZE_MB * 1024 * 1024
    if size > max_bytes:
        raise TranslationValidationError(
            f'El video excede el límite de {settings.TRANSLATION_MAX_FILE_SIZE_MB} MB.'
        )

    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(suffix=extension) as temporary:
        file.seek(0)
        for chunk in file.chunks():
            digest.update(chunk)
            temporary.write(chunk)
        temporary.flush()
        file.seek(0)
        try:
            probe = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration:stream=codec_type',
                    '-of', 'json',
                    temporary.name,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            info = json.loads(probe.stdout or '{}')
        except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise TranslationValidationError('El archivo no es un video válido.') from exc

    stream_types = {stream.get('codec_type') for stream in info.get('streams', [])}
    if 'video' not in stream_types:
        raise TranslationValidationError('El archivo no contiene una pista de video.')
    if 'audio' not in stream_types:
        raise TranslationValidationError('El video no tiene pista de audio.')

    try:
        duration = float(info.get('format', {}).get('duration', 0))
    except (TypeError, ValueError) as exc:
        raise TranslationValidationError('No se pudo determinar la duración del video.') from exc
    if duration <= 0:
        raise TranslationValidationError('El video no tiene una duración válida.')
    max_duration = settings.TRANSLATION_MAX_DURATION_SECONDS
    if duration > max_duration:
        raise TranslationValidationError(
            f'La duración máxima permitida es de {max_duration // 60} minutos.'
        )

    return digest.hexdigest(), duration


def request_translation(
    user: User,
    file: UploadedFile,
    filename: str,
    target_language: str,
    song_title: str | None = None,
    song_artist: str | None = None,
) -> TranslationJob:
    """Valida, reserva créditos, sube el video a R2 y encola el doblaje."""
    from apps.translations.tasks import process_translation_job

    language = (target_language or '').strip().lower()
    if language not in SUPPORTED_LANGUAGES:
        raise TranslationValidationError(
            'Idioma no soportado. Opciones: ' + ', '.join(SUPPORTED_LANGUAGES)
        )
    title = _clean_text(song_title, 'título')
    artist = _clean_text(song_artist, 'artista')
    source_sha256, duration = validate_video_file(file, filename)

    job_id = uuid.uuid4()
    with transaction.atomic():
        locked_user = type(user).objects.select_for_update().get(pk=user.pk)

        # Mismo video y mismo idioma en curso: se devuelve el trabajo existente.
        active_job = (
            TranslationJob.objects.filter(
                user=locked_user,
                source_sha256=source_sha256,
                target_language=language,
                status__in=['queued', 'processing'],
            )
            .order_by('-created_at')
            .first()
        )
        if active_job:
            abandoned = not active_job.source_video_key and (
                timezone.now() - active_job.created_at
            ).total_seconds() > settings.TRANSLATION_REMOTE_TIMEOUT_SECONDS
            if not abandoned:
                return active_job
            _fail_job(active_job, 'La subida del video quedó abandonada.')

        reservation = reserve_credits(
            locked_user,
            amount=settings.TRANSLATION_CREDIT_COST,
            reference_id=str(job_id),
            reference_type=RESERVATION_TYPE,
        )
        try:
            with transaction.atomic():
                job = TranslationJob.objects.create(
                    id=job_id,
                    user=locked_user,
                    source_filename=filename,
                    source_file_size_bytes=file.size,
                    source_sha256=source_sha256,
                    source_duration_seconds=round(duration, 2),
                    target_language=language,
                    song_title=title,
                    song_artist=artist,
                    status='queued',
                    stage='subiendo_video',
                )
        except IntegrityError:
            release_reservation(str(reservation.id))
            existing = TranslationJob.objects.filter(
                user=locked_user,
                source_sha256=source_sha256,
                target_language=language,
                status__in=['queued', 'processing'],
            ).order_by('-created_at').first()
            if existing:
                return existing
            raise

    s3_key = None
    try:
        s3_key = upload_fileobj(file, folder='translations/uploads')
        job.source_video_key = s3_key
        job.stage = 'en_cola'
        job.save(update_fields=['source_video_key', 'stage', 'updated_at'])
        process_translation_job.delay(str(job.id))
    except Exception:
        TranslationJob.objects.filter(id=job.id, status='queued').update(
            status='failed',
            error_message='No se pudo subir el video original.',
            completed_at=timezone.now(),
        )
        release_reservation(str(reservation.id))
        if s3_key:
            try:
                delete_file(s3_key)
            except Exception:
                pass  # La limpieza no debe ocultar el error original.
        raise

    return job


def _fail_job(job: TranslationJob, message: str) -> None:
    reservation = job.user.credit_reservations.filter(
        reference_id=job.id,
        reference_type=RESERVATION_TYPE,
        status='reserved',
    ).first()
    if reservation:
        release_reservation(str(reservation.id))
    job.status = 'failed'
    job.error_message = message
    job.completed_at = timezone.now()
    job.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
