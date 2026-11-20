"""Servicio de validación y encolado para exportaciones de Mix."""

from __future__ import annotations

from django.db import transaction

from apps.credits.services.credit_service import reserve_credits
from apps.mix.models import MixExport, MixProject


def request_mix_export(mix: MixProject, user, data: dict) -> MixExport:
    """Valida parámetros de exportación, reserva créditos y encola el render."""
    if not mix.clips.exists():
        raise ValueError('El mix no tiene clips.')

    export_format = data.get('format', 'mp3')
    quality = data.get('quality', '320k')
    if export_format not in {'mp3', 'wav'}:
        raise ValueError('format debe ser mp3 o wav.')
    if quality not in {'128k', '320k', 'lossless'}:
        raise ValueError('quality no es válida.')
    if export_format == 'wav' and quality != 'lossless':
        raise ValueError('Los archivos WAV deben usar calidad lossless.')
    if export_format == 'mp3' and quality == 'lossless':
        raise ValueError('La calidad lossless requiere formato WAV.')

    requested_muted_ids = data.get('muted_clip_ids', [])
    requested_solo_ids = data.get('solo_clip_ids', [])
    if not isinstance(requested_muted_ids, list) or not isinstance(requested_solo_ids, list):
        raise ValueError('muted_clip_ids y solo_clip_ids deben ser listas.')

    mix_clip_ids = {str(clip_id) for clip_id in mix.clips.values_list('id', flat=True)}
    if not set(map(str, requested_muted_ids)).issubset(mix_clip_ids):
        raise ValueError('Hay clips silenciados que no pertenecen al mix.')
    if not set(map(str, requested_solo_ids)).issubset(mix_clip_ids):
        raise ValueError('Hay clips solo que no pertenecen al mix.')

    with transaction.atomic():
        export = MixExport.objects.create(
            mix_project=mix,
            format=export_format,
            quality=quality,
            status='queued',
        )
        reserve_credits(
            user,
            amount=3,
            reference_id=str(export.id),
            reference_type='mix_export',
        )

    from apps.mix.tasks import render_mix

    tag_ids = list(mix.tags.values_list('id', flat=True))
    render_mix.delay(
        str(export.id),
        tag_ids=tag_ids,
        muted_clip_ids=list(map(str, requested_muted_ids)),
        solo_clip_ids=list(map(str, requested_solo_ids)),
    )
    return export
