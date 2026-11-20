"""Helpers de parseo y orquestación para solicitudes sobre clips de Mix."""

from __future__ import annotations

from django.db import transaction

from apps.mix.models import MixClip, MixProject
from apps.mix.services.mix_service import add_clip, reorder_clips, update_clip


def add_clip_from_payload(mix: MixProject, user, data: dict) -> MixClip:
    """Valida el payload de creación de clip y lo agrega al proyecto."""
    end_time_ms = data.get('end_time_ms')
    if end_time_ms is None:
        raise ValueError('end_time_ms es requerido.')

    is_muted = data.get('is_muted', False)
    is_solo = data.get('is_solo', False)
    if not isinstance(is_muted, bool) or not isinstance(is_solo, bool):
        raise ValueError('is_muted e is_solo deben ser booleanos.')

    return add_clip(
        mix_project=mix,
        user=user,
        position=int(data.get('position', mix.clips.count())),
        timeline_start_ms=int(data.get('timeline_start_ms', 0)),
        song_id=data.get('song_id'),
        stem_file_id=data.get('stem_file_id'),
        start_time_ms=int(data.get('start_time_ms', 0)),
        end_time_ms=int(end_time_ms),
        fade_in_ms=int(data.get('fade_in_ms', 0)),
        fade_out_ms=int(data.get('fade_out_ms', 0)),
        volume=float(data.get('volume', 1.0)),
        is_muted=is_muted,
        is_solo=is_solo,
    )


def patch_clip_from_payload(clip: MixClip, user, data: dict) -> MixClip:
    """Valida el payload de actualización parcial de clip y aplica cambios/reordenamiento."""
    changes: dict = {}
    int_fields = (
        'timeline_start_ms', 'start_time_ms', 'end_time_ms',
        'fade_in_ms', 'fade_out_ms', 'position',
    )
    for field in (*int_fields, 'song_id', 'stem_file_id', 'is_muted', 'is_solo'):
        if field not in data:
            continue
        if field in {'song_id', 'stem_file_id'}:
            changes[field] = data[field]
        elif field in {'is_muted', 'is_solo'}:
            if not isinstance(data[field], bool):
                raise ValueError(f'{field} debe ser booleano.')
            changes[field] = data[field]
        else:
            changes[field] = int(data[field])
    if 'volume' in data:
        changes['volume'] = float(data['volume'])

    if 'song_id' in changes and 'stem_file_id' not in changes:
        changes['stem_file_id'] = None
    if 'stem_file_id' in changes and 'song_id' not in changes:
        changes['song_id'] = None

    requested_position = changes.pop('position', None)
    with transaction.atomic():
        update_clip(clip, user=user, **changes)
        if requested_position is not None:
            clip_count = clip.mix_project.clips.count()
            if requested_position < 0 or requested_position >= clip_count:
                raise ValueError('position está fuera del rango de clips.')
            ordered_ids = list(
                MixClip.objects.filter(mix_project=clip.mix_project)
                .order_by('position')
                .values_list('id', flat=True)
            )
            ordered_ids.remove(clip.id)
            ordered_ids.insert(requested_position, clip.id)
            reorder_clips(clip.mix_project, ordered_ids)
            clip.refresh_from_db()

    return clip
