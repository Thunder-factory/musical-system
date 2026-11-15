from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.conf import settings
from django.utils import timezone

from apps.credits.services.credit_service import (
    InsufficientCreditsError as CreditInsufficientCreditsError,
    reserve_credits,
    release_reservation,
)
from apps.stems.models import StemJob
from apps.stems.tasks import process_stem_job
from ml.storage_client import delete_file, upload_fileobj

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from apps.users.models import User

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB — HU-20


class FileTooLargeError(Exception):
    """Se lanza cuando el archivo de audio supera el límite máximo permitido."""


class AudioValidationError(Exception):
    """Se lanza cuando el archivo no es un MP3/WAV decodificable."""


class InsufficientCreditsError(Exception):
    """Se lanza cuando el usuario no tiene suficientes créditos para la operación."""


def request_stem_separation(user: User, file: UploadedFile, filename: str) -> StemJob:
    """
    Orquesta el flujo completo de separación de stems para un archivo de audio.

    Valida el tamaño del archivo y el balance de créditos del usuario, sube
    el archivo a S3, crea el registro del job en base de datos y encola la
    tarea asíncrona de procesamiento.

    Args:
        user: Usuario que solicita la separación de stems.
        file: Archivo de audio subido (objeto compatible con UploadedFile).
        filename: Nombre original del archivo tal como fue enviado por el cliente.

    Returns:
        Instancia de StemJob recién creada con estado 'queued'.

    Raises:
        FileTooLargeError: Si el archivo supera los 50 MB.
        InsufficientCreditsError: Si el usuario no tiene al menos 2 créditos.
    """
    source_sha256 = validate_audio_file(file, filename)

    import uuid
    job_id = uuid.uuid4()
    reservation = None
    job = None
    with transaction.atomic():
        locked_user = type(user).objects.select_for_update().get(pk=user.pk)
        active_job = (
            StemJob.objects.filter(
                user=locked_user,
                source_sha256=source_sha256,
                status__in=['queued', 'processing'],
            )
            .order_by('-created_at')
            .first()
        )
        if active_job:
            if not active_job.source_audio_url and (
                timezone.now() - active_job.created_at
            ).total_seconds() > settings.STEM_REMOTE_TIMEOUT_SECONDS:
                stale_reservation = active_job.user.credit_reservations.filter(
                    reference_id=active_job.id,
                    reference_type='stem_job',
                    status='reserved',
                ).first()
                if stale_reservation:
                    release_reservation(str(stale_reservation.id))
                active_job.status = 'failed'
                active_job.error_message = 'La subida del archivo quedó abandonada.'
                active_job.completed_at = timezone.now()
                active_job.save(update_fields=['status', 'error_message', 'completed_at'])
                active_job = None
            else:
                return active_job

        if active_job:
            return active_job

        reservation = reserve_credits(
            locked_user,
            amount=2,
            reference_id=str(job_id),
            reference_type='stem_job',
        )

        try:
            with transaction.atomic():
                job = StemJob.objects.create(
                    id=job_id,
                    user=locked_user,
                    source_audio_url='',
                    source_filename=filename,
                    source_file_size_bytes=file.size,
                    source_sha256=source_sha256,
                    status="queued",
                )
        except IntegrityError:
            existing = StemJob.objects.filter(
                user=locked_user,
                source_sha256=source_sha256,
                status__in=['queued', 'processing'],
            ).order_by('-created_at').first()
            if existing:
                release_reservation(str(reservation.id))
                return existing
            raise

    s3_key = None
    try:
        s3_key = upload_fileobj(file, folder="stems/uploads")
        job.source_audio_url = s3_key
        job.save(update_fields=['source_audio_url'])
        process_stem_job.delay(str(job.id))
    except Exception:
        if reservation:
            StemJob.objects.filter(id=job.id, status='queued').update(
                status='failed',
                error_message='No se pudo subir el archivo original.',
                completed_at=timezone.now(),
            )
            release_reservation(str(reservation.id))
        if s3_key:
            try:
                delete_file(s3_key)
            except Exception:
                # La limpieza no debe ocultar el error original.
                pass
        raise

    return job


def validate_audio_file(
    file: UploadedFile,
    filename: str,
    *,
    include_duration: bool = False,
) -> str | tuple[str, float]:
    """Validate extension, bytes and actual decodability before R2 upload."""
    extension = os.path.splitext(filename or '')[1].lower()
    if extension not in {'.mp3', '.wav'}:
        raise AudioValidationError('Solo se aceptan archivos MP3 o WAV.')
    if getattr(file, 'size', 0) <= 0:
        raise AudioValidationError('El archivo de audio está vacío.')
    if file.size > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError('El archivo excede el límite de 50MB.')

    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(suffix=extension) as temporary:
        file.seek(0)
        total = 0
        for chunk in file.chunks():
            total += len(chunk)
            digest.update(chunk)
            temporary.write(chunk)
        file.seek(0)
        if total == 0:
            raise AudioValidationError('El archivo de audio está vacío.')
        try:
            probe = subprocess.run(
                [
                    'ffprobe', '-v', 'error', '-show_entries',
                    'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                    temporary.name,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise AudioValidationError('El archivo no contiene audio decodificable.') from exc

    try:
        duration = float(probe.stdout.strip())
    except ValueError as exc:
        raise AudioValidationError('No se pudo determinar la duración del audio.') from exc
    if duration <= 0:
        raise AudioValidationError('El audio no tiene una duración válida.')
    if duration > settings.STEM_MAX_DURATION_SECONDS:
        raise AudioValidationError(
            f'La duración máxima permitida es {settings.STEM_MAX_DURATION_SECONDS} segundos.'
        )
    fingerprint = digest.hexdigest()
    if include_duration:
        return fingerprint, duration
    return fingerprint


InsufficientCreditsError = CreditInsufficientCreditsError
