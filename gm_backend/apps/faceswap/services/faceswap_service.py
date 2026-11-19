"""Casos de uso del usuario: crear, borrar y descargar jobs de cambio de caras."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.credits.services.credit_service import (
    InsufficientCreditsError as CreditInsufficientCreditsError,
)
from apps.credits.services.credit_service import (
    release_reservation,
    reserve_credits,
)
from apps.faceswap.models import FaceSwapJob, FaceSwapTemplate
from apps.faceswap.services.media_validation import (
    PhotoValidationError,
    VideoValidationError,
    validate_photo,
    validate_video,
)
from apps.faceswap.tasks import process_faceswap_job
from ml.storage_client import delete_file, generate_presigned_url, upload_fileobj

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from apps.users.models import User

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ('queued', 'processing')
REFERENCE_TYPE = 'faceswap_job'

__all__ = [
    'ActiveJobError',
    'FaceSwapRequestError',
    'InsufficientCreditsError',
    'JobNotDeletableError',
    'JobNotReadyError',
    'PhotoValidationError',
    'TemplateUnavailableError',
    'VideoValidationError',
    'delete_job',
    'get_result_url',
    'request_face_swap',
]


class FaceSwapRequestError(Exception):
    """La solicitud no trae foto, consentimiento o exactamente una fuente de video."""


class ActiveJobError(Exception):
    """El usuario ya tiene un face swap en cola o en proceso."""


class TemplateUnavailableError(Exception):
    """La plantilla no existe, está borrada o está inactiva."""


class JobNotDeletableError(Exception):
    """El job todavía se está procesando y no se puede borrar."""


class JobNotReadyError(Exception):
    """El job todavía no tiene un video resultante."""


def _check_request(photo, consent, template_id, video) -> None:
    if not photo:
        raise FaceSwapRequestError('Debes subir una foto de tu cara.')
    if str(consent).strip().lower() != 'true':
        raise FaceSwapRequestError('Debes confirmar que la foto es tuya o tienes permiso.')
    if bool(template_id) == bool(video):
        raise FaceSwapRequestError('Elige una plantilla o sube un clip, no ambos.')


def _get_available_template(template_id) -> FaceSwapTemplate:
    try:
        return FaceSwapTemplate.objects.get(
            id=template_id, is_active=True, deleted_at__isnull=True
        )
    except (FaceSwapTemplate.DoesNotExist, DjangoValidationError, ValueError) as exc:
        # DjangoValidationError/ValueError: el template_id enviado no es un UUID.
        raise TemplateUnavailableError('La plantilla no existe o no está disponible.') from exc


def _release_job_reservation(job_id) -> None:
    from apps.credits.models import CreditReservation

    reservation = CreditReservation.objects.filter(
        reference_id=job_id, reference_type=REFERENCE_TYPE, status='reserved'
    ).first()
    if reservation:
        release_reservation(str(reservation.id))


def _close_abandoned_or_raise(locked_user) -> None:
    """Marca como fallido un job sin foto subida y viejo; si no, lanza ActiveJobError."""
    active = FaceSwapJob.objects.filter(
        user=locked_user, status__in=ACTIVE_STATUSES
    ).order_by('-created_at').first()
    if not active:
        return
    age = (timezone.now() - active.created_at).total_seconds()
    if active.photo_s3_key or age <= settings.FACESWAP_REMOTE_TIMEOUT_SECONDS:
        raise ActiveJobError('Ya tienes un video en proceso. Espera a que termine.')
    _release_job_reservation(active.id)
    active.status = 'failed'
    active.error_message = 'La subida quedó abandonada.'
    active.completed_at = timezone.now()
    active.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])


def _create_job(user: User, job_id, source: dict) -> tuple[FaceSwapJob, object]:
    with transaction.atomic():
        locked_user = type(user).objects.select_for_update().get(pk=user.pk)
        _close_abandoned_or_raise(locked_user)
        reservation = reserve_credits(
            locked_user,
            amount=settings.FACESWAP_CREDIT_COST,
            reference_id=str(job_id),
            reference_type=REFERENCE_TYPE,
        )
        try:
            with transaction.atomic():
                job = FaceSwapJob.objects.create(
                    id=job_id, user=locked_user, status='queued', **source
                )
        except IntegrityError as exc:
            release_reservation(str(reservation.id))
            raise ActiveJobError('Ya tienes un video en proceso. Espera a que termine.') from exc
    return job, reservation


def _upload_and_enqueue(job: FaceSwapJob, reservation, photo, video) -> None:
    uploaded: list[str] = []
    try:
        job.photo_s3_key = upload_fileobj(photo, folder='faceswap/uploads/photos')
        uploaded.append(job.photo_s3_key)
        update_fields = ['photo_s3_key', 'updated_at']
        if video is not None:
            job.source_video_s3_key = upload_fileobj(video, folder='faceswap/uploads/videos')
            uploaded.append(job.source_video_s3_key)
            update_fields.append('source_video_s3_key')
        job.save(update_fields=update_fields)
        process_faceswap_job.delay(str(job.id))
    except Exception:
        FaceSwapJob.objects.filter(id=job.id, status__in=ACTIVE_STATUSES).update(
            status='failed',
            error_message='No se pudo subir los archivos.',
            completed_at=timezone.now(),
        )
        release_reservation(str(reservation.id))
        for key in uploaded:
            try:
                delete_file(key)
            except Exception:
                # La limpieza no debe ocultar el error original.
                logger.exception('No se pudo borrar el archivo subido %s', key)
        raise


def request_face_swap(
    user: User,
    *,
    photo: UploadedFile | None,
    consent,
    template_id: str | None = None,
    video: UploadedFile | None = None,
) -> FaceSwapJob:
    """
    Orquesta la creación de un face swap: valida, reserva créditos, sube y encola.

    Args:
        user: Usuario autenticado que solicita el video.
        photo: Foto de la cara a usar.
        consent: Debe ser ``"true"``: el usuario declara que la foto es suya o tiene permiso.
        template_id: UUID de una plantilla activa (excluyente con ``video``).
        video: Clip propio de hasta 15 s (excluyente con ``template_id``).

    Returns:
        FaceSwapJob recién creado en estado ``queued``.

    Raises:
        FaceSwapRequestError: Si falta foto, consentimiento o la fuente no es única.
        PhotoValidationError / VideoValidationError: Si los archivos no son válidos.
        TemplateUnavailableError: Si la plantilla no está disponible.
        ActiveJobError: Si el usuario ya tiene un job activo.
        InsufficientCreditsError: Si no alcanzan los créditos.
    """
    _check_request(photo, consent, template_id, video)
    validate_photo(photo)
    if video is not None:
        duration = validate_video(video, max_seconds=settings.FACESWAP_MAX_SECONDS)
        source = {
            'source_type': 'upload',
            'source_video_filename': (video.name or '')[:255],
            'source_duration_seconds': duration,
        }
    else:
        template = _get_available_template(template_id)
        source = {
            'source_type': 'template',
            'template': template,
            'source_video_s3_key': template.video_s3_key,
            'source_video_filename': template.title,
            'source_duration_seconds': template.duration_seconds,
            'ref_time_s': template.ref_time_s,
        }

    job, reservation = _create_job(user, uuid.uuid4(), source)
    _upload_and_enqueue(job, reservation, photo, video)
    return job


def get_user_job(user: User, job_id) -> FaceSwapJob:
    """Devuelve un job no borrado del usuario o lanza ``FaceSwapJob.DoesNotExist``."""
    return FaceSwapJob.objects.select_related('template').get(
        id=job_id, user=user, deleted_at__isnull=True
    )


def delete_job(user: User, job_id) -> None:
    """
    Borra lógicamente un job terminado y elimina su MP4 de R2.

    Raises:
        FaceSwapJob.DoesNotExist: Si el job no existe o es de otro usuario.
        JobNotDeletableError: Si el job sigue en cola o en proceso.
    """
    job = get_user_job(user, job_id)
    if job.status in ACTIVE_STATUSES:
        raise JobNotDeletableError('No puedes borrar un video que se está procesando.')
    if job.output_s3_key:
        try:
            delete_file(job.output_s3_key)
        except Exception:
            logger.exception('No se pudo borrar el resultado del face swap %s', job.id)
    job.deleted_at = timezone.now()
    job.save(update_fields=['deleted_at', 'updated_at'])


def get_result_url(user: User, job_id, *, download: bool = False) -> str:
    """
    Genera la URL firmada (1 h) del MP4 resultante.

    Raises:
        FaceSwapJob.DoesNotExist: Si el job no existe o es de otro usuario.
        JobNotReadyError: Si el job no está completado.
    """
    job = get_user_job(user, job_id)
    if not job.has_result:
        raise JobNotReadyError('El video todavía no está listo.')
    disposition = (
        f'attachment; filename="faceswap-{str(job.id)[:8]}.mp4"' if download else None
    )
    return generate_presigned_url(
        job.output_s3_key,
        response_content_disposition=disposition,
        response_content_type='video/mp4',
    )


InsufficientCreditsError = CreditInsufficientCreditsError
