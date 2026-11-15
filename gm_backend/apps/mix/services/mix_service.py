from apps.mix.models import MixProject, MixClip
from django.db import transaction
from django.db.models import F

MIN_VOLUME = 0.01
MAX_VOLUME = 2.0


def _validate_clip_values(*, position, timeline_start_ms, start_time_ms, end_time_ms,
                          fade_in_ms, fade_out_ms, volume):
    if position < 0:
        raise ValueError('position no puede ser negativo.')
    if timeline_start_ms < 0:
        raise ValueError('timeline_start_ms no puede ser negativo.')
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


@transaction.atomic
def add_clip(mix_project: MixProject, *, position: int,
             user=None,
             song_id: str = None, stem_file_id: str = None,
             timeline_start_ms: int = 0,
             start_time_ms: int = 0, end_time_ms: int,
             fade_in_ms: int = 0, fade_out_ms: int = 0,
             volume: float = 1.0, is_muted: bool = False,
             is_solo: bool = False) -> MixClip:
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
        position=position, timeline_start_ms=timeline_start_ms,
        start_time_ms=start_time_ms,
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
        timeline_start_ms=timeline_start_ms,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms,
        volume=volume,
        is_muted=is_muted,
        is_solo=is_solo,
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


def split_clip(clip: MixClip, *, user, playhead_ms: int) -> tuple[MixClip, MixClip]:
    """Divide un clip en dos instancias usando una posición del timeline."""
    if clip.mix_project.user_id != user.pk:
        raise PermissionError('No tenés permiso para editar este clip.')
    if playhead_ms < 0:
        raise ValueError('playhead_ms no puede ser negativo.')

    with transaction.atomic():
        locked_clip = (
            MixClip.objects.select_for_update()
            .select_related('mix_project')
            .get(pk=clip.pk)
        )
        clip_start = locked_clip.timeline_start_ms
        clip_end = clip_start + locked_clip.duration_ms
        if playhead_ms <= clip_start or playhead_ms >= clip_end:
            raise ValueError('El playhead debe estar dentro del clip para dividirlo.')

        source_split = locked_clip.start_time_ms + (playhead_ms - clip_start)
        left_duration = source_split - locked_clip.start_time_ms
        right_duration = locked_clip.end_time_ms - source_split
        if left_duration <= 0 or right_duration <= 0:
            raise ValueError('La división debe dejar dos fragmentos válidos.')

        left_fade_in = min(locked_clip.fade_in_ms, left_duration)
        left_fade_out = min(locked_clip.fade_out_ms, left_duration)
        right_fade_in = min(locked_clip.fade_in_ms, right_duration)
        right_fade_out = min(locked_clip.fade_out_ms, right_duration)

        locked_clip.end_time_ms = source_split
        locked_clip.fade_in_ms = left_fade_in
        locked_clip.fade_out_ms = left_fade_out
        locked_clip.save(update_fields=['end_time_ms', 'fade_in_ms', 'fade_out_ms'])

        MixClip.objects.filter(
            mix_project=locked_clip.mix_project,
            position__gt=locked_clip.position,
        ).update(position=F('position') + 1)

        right_clip = MixClip.objects.create(
            mix_project=locked_clip.mix_project,
            song=locked_clip.song,
            stem_file=locked_clip.stem_file,
            custom_audio_s3_key=locked_clip.custom_audio_s3_key,
            position=locked_clip.position + 1,
            timeline_start_ms=playhead_ms,
            start_time_ms=source_split,
            end_time_ms=clip_end - clip_start + locked_clip.start_time_ms,
            fade_in_ms=right_fade_in,
            fade_out_ms=right_fade_out,
            volume=locked_clip.volume,
            is_muted=locked_clip.is_muted,
            is_solo=locked_clip.is_solo,
        )

    return locked_clip, right_clip


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
        for field in (
            'position', 'timeline_start_ms', 'start_time_ms', 'end_time_ms',
            'fade_in_ms', 'fade_out_ms', 'volume', 'is_muted', 'is_solo',
        )
    }
    _validate_clip_values(
        position=values['position'],
        timeline_start_ms=values['timeline_start_ms'],
        start_time_ms=values['start_time_ms'],
        end_time_ms=values['end_time_ms'],
        fade_in_ms=values['fade_in_ms'],
        fade_out_ms=values['fade_out_ms'],
        volume=values['volume'],
    )
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
    with transaction.atomic():
        clip = MixClip.objects.select_for_update().select_related('mix_project').get(id=clip_id)
        mix = MixProject.objects.select_for_update().get(pk=clip.mix_project_id)
        if str(mix.user_id) != str(user.id):
            raise PermissionError("No tenés permiso para eliminar este clip.")
        position = clip.position
        clip.delete()
        MixClip.objects.filter(mix_project=mix, position__gt=position).update(
            position=F('position') - 1
        )
