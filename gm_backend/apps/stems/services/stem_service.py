from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from django.db import transaction

from apps.credits.services.credit_service import check_balance
from apps.stems.models import StemJob
from apps.stems.tasks import process_stem_job
from ml.storage_client import upload_fileobj

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from apps.users.models import User

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB — HU-20


class FileTooLargeError(Exception):
    """Se lanza cuando el archivo de audio supera el límite máximo permitido."""


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
    # HU-20: rechazar archivos muy grandes
    if file.size > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError("El archivo excede el límite de 50MB.")

    digest = hashlib.sha256()
    for chunk in file.chunks():
        digest.update(chunk)
    source_sha256 = digest.hexdigest()
    file.seek(0)

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
            return active_job

        active_jobs_count = StemJob.objects.filter(
            user=locked_user,
            status__in=['queued', 'processing'],
        ).count()
        required_credits = 2 * (active_jobs_count + 1)
        if not check_balance(locked_user, required=required_credits):
            raise InsufficientCreditsError(
                f"Necesitas {required_credits} créditos disponibles para iniciar otra separación."
            )

        # Subir el archivo original a S3
        s3_key = upload_fileobj(file, folder="stems/uploads")

        job = StemJob.objects.create(
            user=locked_user,
            source_audio_url=s3_key,
            source_filename=filename,
            source_file_size_bytes=file.size,
            source_sha256=source_sha256,
            status="queued",
        )

        transaction.on_commit(lambda: process_stem_job.delay(str(job.id)))

    return job
