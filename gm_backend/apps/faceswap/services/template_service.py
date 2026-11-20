"""Casos de uso del admin: catálogo de plantillas de video para el cambio de caras."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

from apps.faceswap.models import FaceSwapTemplate
from apps.faceswap.services.media_validation import (
    extract_thumbnail,
    validate_photo,
    validate_video,
)
from ml.storage_client import delete_file, upload_file, upload_fileobj

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024
_UNSET = object()


class TemplateValidationError(Exception):
    """Los datos de la plantilla no son válidos (título, video o segundo de referencia)."""


def _check_ref_time(ref_time_s: float | None, duration: float) -> None:
    if ref_time_s is not None and not 0 <= ref_time_s <= duration:
        raise TemplateValidationError('El segundo de referencia está fuera del video.')


def _generate_thumbnail(video: UploadedFile, at_s: float) -> str:
    """Copia el video a disco, extrae un fotograma y lo sube a R2; devuelve la clave."""
    extension = os.path.splitext(video.name or '')[1].lower()
    thumb_path = None
    with tempfile.NamedTemporaryFile(suffix=extension) as temporary:
        video.seek(0)
        for chunk in video.chunks():
            temporary.write(chunk)
        temporary.flush()
        video.seek(0)
        try:
            thumb_path = extract_thumbnail(temporary.name, at_s)
            key = f'faceswap/templates/thumbnails/{uuid.uuid4()}.jpg'
            upload_file(str(thumb_path), key)
        finally:
            if thumb_path:
                thumb_path.unlink(missing_ok=True)
    return key


def _delete_keys(keys: list[str]) -> None:
    for key in keys:
        try:
            delete_file(key)
        except Exception:
            logger.exception('No se pudo borrar el archivo de plantilla %s', key)


def create_template(
    *,
    title: str,
    video: UploadedFile | None,
    thumbnail: UploadedFile | None = None,
    ref_time_s: float | None = None,
    is_active: bool = True,
) -> FaceSwapTemplate:
    """
    Valida y sube una plantilla nueva (video + miniatura subida o generada con ffmpeg).

    Raises:
        TemplateValidationError: Si falta el video o ``ref_time_s`` está fuera del video.
        PhotoValidationError / VideoValidationError: Si los archivos no son válidos.
    """
    if not video:
        raise TemplateValidationError('Debes subir el video de la plantilla.')
    duration = validate_video(video, max_seconds=settings.FACESWAP_MAX_SECONDS)
    _check_ref_time(ref_time_s, duration)
    if thumbnail:
        validate_photo(thumbnail, max_bytes=MAX_THUMBNAIL_BYTES)

    uploaded: list[str] = []
    try:
        # La miniatura va primero: boto3.upload_fileobj cierra el archivo al terminar,
        # así que el video ya no se puede leer después de subirlo.
        if thumbnail:
            thumb_key = upload_fileobj(thumbnail, folder='faceswap/templates/thumbnails')
        else:
            at_s = ref_time_s if ref_time_s is not None else min(1.0, duration / 2)
            thumb_key = _generate_thumbnail(video, at_s)
        uploaded.append(thumb_key)
        video_key = upload_fileobj(video, folder='faceswap/templates/videos')
        uploaded.append(video_key)
        return FaceSwapTemplate.objects.create(
            title=title.strip(),
            video_s3_key=video_key,
            thumbnail_s3_key=thumb_key,
            duration_seconds=duration,
            ref_time_s=ref_time_s,
            is_active=is_active,
        )
    except Exception:
        _delete_keys(uploaded)
        raise


def get_template(template_id) -> FaceSwapTemplate:
    """Devuelve una plantilla no borrada o lanza ``FaceSwapTemplate.DoesNotExist``."""
    return FaceSwapTemplate.objects.get(id=template_id, deleted_at__isnull=True)


def update_template(
    template_id,
    *,
    title: str | None = None,
    ref_time_s=_UNSET,
    is_active: bool | None = None,
    thumbnail: UploadedFile | None = None,
) -> FaceSwapTemplate:
    """
    Actualiza título, segundo de referencia, estado y/o miniatura (el video no se cambia).

    Args:
        template_id: UUID de la plantilla.
        title: Nuevo título (opcional).
        ref_time_s: Nuevo segundo de referencia; ``None`` lo borra; omitido no lo toca.
        is_active: Activa o desactiva la plantilla.
        thumbnail: Nueva miniatura (se borra la anterior de R2).

    Raises:
        FaceSwapTemplate.DoesNotExist: Si no existe o está borrada.
        TemplateValidationError / PhotoValidationError: Si los datos no son válidos.
    """
    template = get_template(template_id)
    if ref_time_s is not _UNSET:
        _check_ref_time(ref_time_s, template.duration_seconds)
        template.ref_time_s = ref_time_s
    if title is not None:
        template.title = title.strip()
    if is_active is not None:
        template.is_active = is_active
    old_thumbnail = None
    if thumbnail:
        validate_photo(thumbnail, max_bytes=MAX_THUMBNAIL_BYTES)
        old_thumbnail = template.thumbnail_s3_key
        template.thumbnail_s3_key = upload_fileobj(
            thumbnail, folder='faceswap/templates/thumbnails'
        )
    template.save()
    if old_thumbnail:
        _delete_keys([old_thumbnail])
    return template


def soft_delete_template(template_id) -> None:
    """
    Borra lógicamente una plantilla (deleted_at + is_active=False); R2 no se toca.

    Raises:
        FaceSwapTemplate.DoesNotExist: Si no existe o ya estaba borrada.
    """
    template = get_template(template_id)
    template.is_active = False
    template.deleted_at = timezone.now()
    template.save(update_fields=['is_active', 'deleted_at', 'updated_at'])
