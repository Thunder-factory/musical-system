"""Service for registering user-owned audio files as ready Songs."""

from __future__ import annotations

import os
import logging

from django.db import IntegrityError

from apps.stems.services.stem_service import (
    AudioValidationError,
    FileTooLargeError,
    validate_audio_file,
)
from ml.storage_client import delete_file, upload_fileobj

logger = logging.getLogger(__name__)


def upload_song(user, audio_file, *, title: str | None = None):
    """Validate, upload and register an external song without charging credits."""
    filename = getattr(audio_file, 'name', '') or ''
    source_sha256, duration = validate_audio_file(
        audio_file,
        filename,
        include_duration=True,
    )

    clean_title = (title or os.path.splitext(os.path.basename(filename))[0]).strip()
    if not clean_title:
        raise ValueError('El título de la canción es obligatorio.')
    clean_title = clean_title[:200]

    from apps.songs.models import Song
    existing = Song.objects.filter(
        user=user,
        source_type='uploaded',
        source_sha256=source_sha256,
        deleted_at__isnull=True,
    ).first()
    if existing:
        return existing

    object_key = None
    try:
        object_key = upload_fileobj(audio_file, folder=f'songs/uploads/{user.pk}')
        try:
            return Song.objects.create(
                user=user,
                title=clean_title,
                source_type='uploaded',
                source_sha256=source_sha256,
                audio_duration=duration,
                audio_s3_key=object_key,
                status='ready',
                is_public=False,
                instrumental=False,
                lyrics_source='user',
            )
        except IntegrityError:
            # A concurrent identical request won the unique constraint.
            existing = Song.objects.filter(
                user=user,
                source_type='uploaded',
                source_sha256=source_sha256,
                deleted_at__isnull=True,
            ).first()
            if existing:
                try:
                    delete_file(object_key)
                except Exception:
                    logger.exception(
                        'No se pudo eliminar la subida duplicada %s',
                        object_key,
                    )
                object_key = None
                return existing
            raise
    except Exception:
        if object_key:
            try:
                delete_file(object_key)
            except Exception:
                # Preserve the database/upload error; cleanup is compensatory.
                pass
        raise
