# apps/songs/services/generation_service.py
from django.db import transaction

from apps.songs.models import Song, GenerationJob, Tag, SongTag


def request_generation(user, *, title: str, description: str = None,
                       prompt: str = None, lyrics: str = None,
                       described_lyrics: str = None,
                       instrumental: bool = False,
                       vocal_type: str = 'auto',
                       language: str = 'auto',
                       guidance_scale: float = 10.0,
                       infer_step: int = 100,
                       audio_duration: float = 180.0
                       ) -> GenerationJob:
    """
    Punto de entrada para generar una canción.
    Valida créditos → crea Song + Job → encola tarea Celery.
    El modelo ML local no interviene aquí: su rol es potenciar las recomendaciones.
    """
    from apps.credits.services.credit_service import (
        InsufficientCreditsError as CreditInsufficientCreditsError,
        reserve_credits,
    )

    mode = _determine_mode(description, prompt, lyrics, described_lyrics)

    try:
        with transaction.atomic():
            song = Song.objects.create(
                user=user,
                title=_default_title(title, description, described_lyrics),
                description=description,
                prompt=prompt,
                lyrics=lyrics,
                described_lyrics=described_lyrics,
                instrumental=instrumental,
                vocal_type=vocal_type,
                language=language,
                guidance_scale=guidance_scale,
                infer_step=infer_step,
                audio_duration=audio_duration,
                status='draft',
            )
            job = GenerationJob.objects.create(user=user, song=song, mode=mode, status='queued')
            reserve_credits(
                user,
                amount=1,
                reference_id=str(job.id),
                reference_type='generation_job',
            )
            from apps.songs.tasks import process_generation_job
            transaction.on_commit(
                lambda job_id=str(job.id): process_generation_job.delay(job_id)
            )
    except CreditInsufficientCreditsError as exc:
        raise InsufficientCreditsError(str(exc)) from exc

    return job


def _determine_mode(description, prompt, lyrics, described_lyrics) -> str:
    if description:
        return 'from_description'
    elif lyrics and prompt:
        return 'with_lyrics'
    elif described_lyrics and prompt:
        return 'with_described_lyrics'
    raise ValueError("Parámetros insuficientes para determinar el modo.")


def _default_title(title, description, described_lyrics) -> str:
    raw = title or description or described_lyrics or "Untitled"
    return (raw[:1].upper() + raw[1:].strip())[:199]


class InsufficientCreditsError(Exception):
    pass
