"""Selección final de versión del tarareo y conversión a Song en biblioteca."""

from __future__ import annotations

import logging

from django.db import transaction

from apps.humming.models import HummingJob

logger = logging.getLogger(__name__)


def _find_version(job: HummingJob, number: int) -> dict | None:
    for version in job.versions:
        if int(version.get('numero', 0)) == number:
            return version
    return None


def _delete_keys(keys: list[str]) -> None:
    from ml.storage_client import delete_file

    for key in keys:
        try:
            delete_file(key)
        except Exception:
            logger.exception('No se pudo borrar %s de R2', key)


def choose_version(job: HummingJob, number: int, *, title: str | None = None):
    """Crea la Song de la versión elegida de forma idempotente."""
    from apps.humming import services as pkg
    from apps.humming.enhancement import automatic_for
    from apps.songs.models import Song, SongTag, Tag

    with transaction.atomic():
        job = HummingJob.objects.select_for_update().get(id=job.id)
        if job.status != 'completed':
            raise ValueError('El tarareo todavía no terminó de procesarse.')
        if job.song_id:
            if job.chosen_version == number:
                return job.song
            raise ValueError('Ya elegiste otra versión de este tarareo.')

        version = _find_version(job, number)
        if not version:
            raise ValueError('Esa versión no existe para este tarareo.')
        song_file = version.get('cancion') or ''
        if song_file not in (job.available_outputs or []):
            raise ValueError('El audio de esa versión no está disponible.')

        ia = automatic_for(job, number)
        if ia and ia.status in ('queued', 'processing'):
            raise ValueError('Esa versión todavía se está produciendo con IA.')
        usa_ia = bool(ia and ia.status == 'completed' and ia.variant_keys)
        audio_key = ia.variant_keys[0] if usa_ia else job.output_keys[song_file]

        metadata = job.metadata or {}
        style = (version.get('estilo') or metadata.get('estilo') or '').strip()
        clean_title = (title or job.title or '').strip()[:200]
        if not clean_title:
            clean_title = f'Mi tarareo ({style})' if style else 'Mi tarareo'

        song = Song.objects.create(
            user=job.user,
            title=clean_title,
            source_type='hummed',
            description=metadata.get('estiloMensaje') or None,
            prompt=style or None,
            instrumental=True,
            lyrics_source='user',
            audio_duration=float(metadata.get('duracionCancionSegundos') or 0),
            audio_s3_key=audio_key,
            thumbnail_s3_key=ia.cover_s3_key if usa_ia else None,
            status='ready',
            is_public=False,
        )
        if usa_ia:
            ia.song = song
            ia.chosen_variant = 1
            ia.save(update_fields=['song', 'chosen_variant', 'updated_at'])
            descartadas = []
            for otra in job.enhancements.filter(automatic=True, status='completed').exclude(id=ia.id):
                descartadas += [*(otra.variant_keys or []), otra.cover_s3_key]
            transaction.on_commit(lambda: pkg._delete_keys([k for k in descartadas if k]))
        if style:
            tag, _ = Tag.objects.get_or_create(name=style.lower(), defaults={'category': 'genre'})
            SongTag.objects.get_or_create(song=song, tag=tag)

        job.song = song
        job.chosen_version = number
        job.save(update_fields=['song', 'chosen_version', 'updated_at'])
        return song
