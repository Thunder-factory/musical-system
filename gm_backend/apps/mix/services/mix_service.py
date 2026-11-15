from apps.mix.models import MixProject, MixClip
from django.db import transaction
from django.db.models import F

MIN_VOLUME = 0.01
MAX_VOLUME = 2.0


def _validate_clip_values(*, position, start_time_ms, end_time_ms,
                          fade_in_ms, fade_out_ms, volume):
    if position < 0:
        raise ValueError('position no puede ser negativo.')
    if start_time_ms < 0 or end_time_ms <= start_time_ms:
        raise ValueError('El rango de tiempo del clip no es válido.')
    duration = end_time_ms - start_time_ms
    if fade_in_ms < 0 or fade_out_ms < 0:
        raise ValueError('Los fades no pueden ser negativos.')
    if fade_in_ms > duration or fade_out_ms > duration:
        raise ValueError('Los fades no pueden superar la duración del clip.')
    if not MIN_VOLUME <= volume <= MAX_VOLUME:
        raise ValueError(f'El volumen debe estar entre {MIN_VOLUME} y {MAX_VOLUME}.')


def _resolve_source(user, song_id=None, stem_file_id=None):
    if bool(song_id) == bool(stem_file_id):
        raise ValueError('Debe proporcionarse exactamente song_id o stem_file_id.')

    if song_id:
        from apps.songs.models import Song
        from django.db.models import Q
        try:
            song = Song.objects.get(
                Q(id=song_id) & (Q(user=user) | Q(is_public=True)),
                status='ready',
            )
            return {'song': song}
        except Song.DoesNotExist as exc:
            raise ValueError('La canción no existe, no está lista o no es accesible.') from exc

    from apps.stems.models import StemFile
    try:
        stem_file = StemFile.objects.select_related('stem_job').get(
            id=stem_file_id,
            stem_job__user=user,
            stem_job__status='completed',
        )
        return {'stem_file': stem_file}
    except StemFile.DoesNotExist as exc:
        raise ValueError('El stem no existe, no está listo o no es accesible.') from exc


def create_mix_project(user, title: str, description: str = None, bpm: int = None) -> MixProject:
    return MixProject.objects.create(
        user=user, title=title, description=description, bpm=bpm, status='draft',
    )


def add_clip(mix_project: MixProject, *, position: int,
             user=None,
             song_id: str = None, stem_file_id: str = None,
             start_time_ms: int = 0, end_time_ms: int,
             fade_in_ms: int = 0, fade_out_ms: int = 0,
             volume: float = 1.0) -> MixClip:
    """Agrega un clip al mix. Valida fuente y rango de tiempo."""
    if user is None:
        user = mix_project.user
    if position < 0 or position > mix_project.clips.count():
        raise ValueError('position está fuera del rango de clips.')
    source = _resolve_source(user, song_id, stem_file_id)
    source_obj = next(iter(source.values()))
    if not getattr(source_obj, 'audio_s3_key', None):
        raise ValueError('La fuente no tiene un archivo de audio disponible.')
    source_duration = getattr(source_obj, 'audio_duration', None)
    if source_duration is None:
        source_duration = (getattr(source_obj, 'duration_seconds', None) or 0)
    if source_duration and end_time_ms > int(float(source_duration) * 1000):
        raise ValueError('El clip supera la duración registrada del audio.')
    _validate_clip_values(
        position=position, start_time_ms=start_time_ms,
        end_time_ms=end_time_ms, fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms, volume=volume,
    )

    # Desplazar clips existentes para dejar espacio en la posición pedida
    MixClip.objects.filter(
        mix_project=mix_project, position__gte=position
    ).update(position=F('position') + 1)

    return MixClip.objects.create(
        mix_project=mix_project,
        **source,
        position=position,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms,
        volume=volume,
    )


def reorder_clips(mix_project: MixProject, clip_order: list) -> None:
    """Reordena los clips. clip_order: lista de UUIDs (str) en el nuevo orden."""
    with transaction.atomic():
        locked_mix = MixProject.objects.select_for_update().get(pk=mix_project.pk)
        current_ids = list(
            MixClip.objects.select_for_update()
            .filter(mix_project=locked_mix)
            .values_list('id', flat=True)
        )
        try:
            requested_ids = [str(clip_id) for clip_id in clip_order]
            current_id_strings = {str(clip_id) for clip_id in current_ids}
        except (TypeError, ValueError) as exc:
            raise ValueError('clip_ids debe ser una lista válida.') from exc
        if len(requested_ids) != len(current_ids) or len(set(requested_ids)) != len(requested_ids):
            raise ValueError('La reordenación debe incluir cada clip exactamente una vez.')
        if set(requested_ids) != current_id_strings:
            raise ValueError('La reordenación contiene clips que no pertenecen al mix.')
        # Las posiciones negativas temporales evitan colisiones dentro de la transacción.
        for new_position, clip_id in enumerate(requested_ids):
            MixClip.objects.filter(id=clip_id, mix_project=locked_mix).update(
                position=-(new_position + 1)
            )
        for new_position, clip_id in enumerate(requested_ids):
            MixClip.objects.filter(id=clip_id, mix_project=locked_mix).update(
                position=new_position
            )


def update_clip(clip: MixClip, *, user, **changes) -> MixClip:
    if clip.mix_project.user_id != user.pk:
        raise PermissionError('No tenés permiso para editar este clip.')
    source_fields = {'song_id', 'stem_file_id'} & changes.keys()
    if source_fields:
        source = _resolve_source(
            user,
            changes.get('song_id', clip.song_id),
            changes.get('stem_file_id', clip.stem_file_id),
        )
        clip.song = source.get('song')
        clip.stem_file = source.get('stem_file')
    values = {
        field: changes.get(field, getattr(clip, field))
        for field in ('position', 'start_time_ms', 'end_time_ms', 'fade_in_ms', 'fade_out_ms', 'volume')
    }
    _validate_clip_values(**values)
    source_obj = clip.song or clip.stem_file
    if not getattr(source_obj, 'audio_s3_key', None):
        raise ValueError('La fuente no tiene un archivo de audio disponible.')
    source_duration = getattr(source_obj, 'audio_duration', None)
    if source_duration is None:
        source_duration = getattr(source_obj, 'duration_seconds', None) or 0
    if source_duration and values['end_time_ms'] > int(float(source_duration) * 1000):
        raise ValueError('El clip supera la duración registrada del audio.')
    for field, value in values.items():
        setattr(clip, field, value)
    clip.save()
    return clip


def remove_clip(clip_id: str, user) -> None:
    """Elimina un clip verificando que el mix sea del usuario."""
    clip = MixClip.objects.select_related('mix_project').get(id=clip_id)
    if str(clip.mix_project.user_id) != str(user.id):
        raise PermissionError("No tenés permiso para eliminar este clip.")
    clip.delete()
