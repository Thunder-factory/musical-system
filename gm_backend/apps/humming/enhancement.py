"""
"Mejorar con IA": produce una versión del tarareo con ACE-Step 1.5 en Modal.

La versión de FluidSynth (ya en R2) se usa como audio de origen del modo
cover, que cambia estilo e instrumentación conservando la melodía. El estilo lo elige el usuario de un catálogo amplio o lo
escribe libremente; el BPM y la tonalidad salen del análisis del tarareo.

Cada pedido genera HUMMING_ENHANCE_VARIANTS variantes en una sola pasada y
cobra HUMMING_ENHANCE_CREDIT_COST por el lote. El usuario escucha y elige una:
solo esa se guarda como Song; las demás se borran de R2 (igual que las
versiones del tarareo que no se eligen).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.credits.services.credit_service import (
    InsufficientCreditsError,
    confirm_reservation,
    release_reservation,
    reserve_credits,
)
from apps.humming.models import HummingEnhancement, HummingJob
from apps.humming.styles import (
    CUSTOM_STYLE_KEY,
    DEFAULT_FIDELITY,
    FIDELITY_STRENGTH,
    STYLES_BY_KEY,
    WORKER_PRESETS,
    build_prompt,
    pick_base_version,
)

logger = logging.getLogger(__name__)

RESERVATION_TYPE = 'humming_enhancement'
MAX_CUSTOM_STYLE_LENGTH = 200


class EnhancementUnavailableError(RuntimeError):
    """La mejora con IA no está configurada (falta el endpoint de Modal)."""


def _version_song_file(job: HummingJob, number: int) -> str:
    for version in job.versions:
        if int(version.get('numero', 0)) == number:
            return version.get('cancion') or ''
    return ''


def request_enhancement(
    job: HummingJob,
    *,
    version: int | None = None,
    style: str,
    custom_style: str | None = None,
    fidelity: str = DEFAULT_FIDELITY,
) -> HummingEnhancement:
    """
    Valida, reserva créditos y encola la mejora. No llama a Modal en la request.

    Sin `version`, la base se elige sola según el estilo (`pick_base_version`):
    el usuario solo dice "quiero caporales" y se parte de la versión más parecida.
    """
    if not settings.MODAL_ENDPOINT_FROM_REFERENCE:
        raise EnhancementUnavailableError('La mejora con IA no está disponible por ahora.')
    if job.status != 'completed':
        raise ValueError('El tarareo todavía no terminó de procesarse.')
    if version is None:
        listas = [v for v in job.versions if (v.get('cancion') or '') in (job.available_outputs or [])]
        version = pick_base_version(style, listas)
        if version is None:
            raise ValueError('El tarareo no tiene versiones disponibles.')

    song_file = _version_song_file(job, version)
    if not song_file or song_file not in (job.available_outputs or []):
        raise ValueError('Esa versión no está disponible.')

    if style == CUSTOM_STYLE_KEY:
        text = (custom_style or '').strip()
        if not text:
            raise ValueError('Describe el estilo que quieres.')
        tags, label = text[:MAX_CUSTOM_STYLE_LENGTH], text[:60]
    elif style in STYLES_BY_KEY:
        tags, label = STYLES_BY_KEY[style].tags, STYLES_BY_KEY[style].label
    else:
        raise ValueError('Estilo desconocido.')

    if fidelity not in FIDELITY_STRENGTH:
        raise ValueError('Fidelidad desconocida.')

    enhancement = HummingEnhancement.objects.create(
        humming_job=job,
        user=job.user,
        version_number=version,
        style_key=style,
        style_label=label,
        prompt=build_prompt(tags, job.metadata),
        fidelity=fidelity,
        ref_audio_strength=FIDELITY_STRENGTH[fidelity],
    )
    try:
        reserve_credits(
            job.user,
            amount=settings.HUMMING_ENHANCE_CREDIT_COST,
            reference_id=str(enhancement.id),
            reference_type=RESERVATION_TYPE,
            expires_in_seconds=settings.HUMMING_ENHANCE_STALE_SECONDS + 600,
        )
    except InsufficientCreditsError:
        enhancement.delete()
        raise

    from apps.humming.tasks import submit_humming_enhancement

    transaction.on_commit(lambda: submit_humming_enhancement.delay(str(enhancement.id)))
    return enhancement


def build_modal_body(enhancement: HummingEnhancement) -> dict:
    job = enhancement.humming_job
    song_file = _version_song_file(job, enhancement.version_number)
    metadata = job.metadata or {}
    duration = float(metadata.get('duracionCancionSegundos') or 90)
    bpm = metadata.get('bpm')
    return {
        'prompt': enhancement.prompt,
        'ref_s3_key': job.output_keys[song_file],
        'ref_audio_strength': enhancement.ref_audio_strength,
        'audio_duration': duration,
        'bpm': int(round(bpm)) if isinstance(bpm, (int, float)) and bpm > 0 else None,
        'keyscale': metadata.get('tonalidad') or '',
        'instrumental': True,
        # Automáticas: una por versión del tarareo; del panel: varias para elegir.
        'variants': 1 if enhancement.automatic else settings.HUMMING_ENHANCE_VARIANTS,
        'client_job_id': str(enhancement.id),
    }


def mark_submitted(enhancement_id: str, remote_job_id: str) -> None:
    HummingEnhancement.objects.filter(id=enhancement_id, status='queued').update(
        status='processing',
        remote_job_id=remote_job_id,
        progress=10,
        started_at=timezone.now(),
        updated_at=timezone.now(),
    )


def mark_failed(enhancement_id: str, message: str) -> None:
    failed_enhancement = None
    with transaction.atomic():
        enhancement = HummingEnhancement.objects.select_for_update().get(id=enhancement_id)
        if enhancement.is_terminal:
            return
        enhancement.status = 'failed'
        enhancement.error_message = message[:1000]
        enhancement.completed_at = timezone.now()
        enhancement.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
        failed_enhancement = enhancement
    try:
        _release(enhancement_id)
    except Exception:
        logger.exception('No se pudo liberar la reserva de la mejora %s', enhancement_id)
    if failed_enhancement:
        try:
            from apps.notifications.services import notify_user

            notify_user(
                failed_enhancement.user,
                type='humming_failed',
                reference_id=str(failed_enhancement.id),
                title='No se pudo mejorar el tarareo',
                message=f'Falló la mejora con IA: {message[:900]}',
                push_message='La mejora con IA de tu tarareo no pudo completarse.',
            )
        except Exception:
            logger.exception(
                'No se pudo notificar la mejora fallida %s', enhancement_id,
            )


def _release(enhancement_id: str) -> None:
    from apps.credits.models import CreditReservation

    reservation = CreditReservation.objects.filter(
        reference_id=enhancement_id, reference_type=RESERVATION_TYPE, status='reserved'
    ).first()
    if reservation:
        release_reservation(str(reservation.id))


def complete(enhancement_id: str, result: dict) -> bool:
    """Guarda las variantes de Modal y confirma el cobro del lote. Idempotente."""
    from apps.credits.models import CreditReservation

    variantes = [key for key in (result.get('variant_keys') or [result.get('s3_key')]) if key]
    if not variantes:
        raise ValueError('Modal devolvió un resultado sin audio.')

    with transaction.atomic():
        enhancement = HummingEnhancement.objects.select_for_update().get(id=enhancement_id)
        if enhancement.is_terminal:
            return False

        reservation = CreditReservation.objects.filter(
            reference_id=str(enhancement.id), reference_type=RESERVATION_TYPE
        ).first()
        credits = 0
        if reservation:
            try:
                confirm_reservation(str(reservation.id))
                credits = reservation.amount
            except (ValueError, InsufficientCreditsError) as exc:
                logger.warning('No se pudo cobrar la mejora %s: %s', enhancement.id, exc)

        enhancement.variant_keys = variantes
        enhancement.cover_s3_key = result.get('cover_image_s3_key') or None
        enhancement.status = 'completed'
        enhancement.progress = 100
        enhancement.credits_used = credits
        enhancement.completed_at = timezone.now()
        enhancement.save()

    if settings.HUMMING_SIMILARITY:
        from apps.humming.tasks import measure_humming_similarity

        transaction.on_commit(lambda: measure_humming_similarity.delay(enhancement_id))
    if enhancement.automatic:
        return True  # forma parte del tarareo: no se notifica por separado
    try:
        from apps.notifications.services import notify_user

        cuantas = len(variantes)
        notify_user(
            enhancement.user,
            type='humming_ready',
            reference_id=str(enhancement.id),
            title='✨ Tu tarareo mejorado está listo',
            message=(f'Escucha las {cuantas} versiones en estilo {enhancement.style_label} '
                     'y elige la que más te guste.' if cuantas > 1 else
                     f'Tu versión en estilo {enhancement.style_label} está lista.'),
        )
    except Exception:
        logger.exception('No se pudo notificar la mejora %s', enhancement_id)
    return True


def choose_variant(enhancement: HummingEnhancement, number: int):
    """
    Guarda la variante elegida como Song y borra las demás de R2.

    Idempotente para la misma variante; elegir otra después da error.
    """
    from apps.songs.models import Song, SongTag, Tag

    with transaction.atomic():
        # of=('self',): Postgres no permite FOR UPDATE sobre el lado nulo de un
        # LEFT JOIN (song puede ser nulo); se bloquea solo la fila de la mejora.
        enhancement = (
            HummingEnhancement.objects.select_for_update(of=('self',))
            .select_related('humming_job', 'song')
            .get(id=enhancement.id)
        )
        if enhancement.status != 'completed':
            raise ValueError('La mejora todavía no está lista.')
        if enhancement.song_id:
            if enhancement.chosen_variant == number:
                return enhancement.song
            raise ValueError('Ya elegiste otra versión de esta mejora.')
        if not 1 <= number <= len(enhancement.variant_keys or []):
            raise ValueError('Esa versión no existe.')

        job = enhancement.humming_job
        base_title = job.title or 'Mi tarareo'
        song = Song.objects.create(
            user=enhancement.user,
            title=f'{base_title} · {enhancement.style_label}'[:200],
            source_type='hummed',
            description=f'Tarareo producido con IA en estilo {enhancement.style_label}.',
            prompt=enhancement.prompt,
            instrumental=True,
            lyrics_source='user',
            audio_duration=float((job.metadata or {}).get('duracionCancionSegundos') or 0),
            audio_s3_key=enhancement.variant_keys[number - 1],
            thumbnail_s3_key=enhancement.cover_s3_key,
            status='ready',
            is_public=False,
        )
        clean = enhancement.style_label.strip().lower()[:50]
        if clean:
            tag, _ = Tag.objects.get_or_create(name=clean, defaults={'category': 'genre'})
            SongTag.objects.get_or_create(song=song, tag=tag)

        descartadas = [key for i, key in enumerate(enhancement.variant_keys, start=1) if i != number]
        enhancement.song = song
        enhancement.chosen_variant = number
        enhancement.save(update_fields=['song', 'chosen_variant', 'updated_at'])
        transaction.on_commit(lambda: _delete_keys(descartadas))
    return song


def arrangement_name(number: int) -> str:
    return 'arreglo.mid' if number == 1 else f'arreglo-{number}.mid'


def measure_similarity(enhancement_id: str) -> list[dict]:
    """
    Pide al worker cuánto de la melodía del tarareo suena en cada variante y lo
    guarda. Es informativo: si falla, la versión con IA sigue disponible igual.
    """
    import requests

    from ml.storage_client import generate_presigned_url

    item = HummingEnhancement.objects.select_related('humming_job').get(id=enhancement_id)
    arrangement = (item.humming_job.output_keys or {}).get(arrangement_name(item.version_number))
    if item.status != 'completed' or not item.variant_keys or not arrangement:
        return []
    seconds = 900
    response = requests.post(
        f"{settings.TARAREO_URL.rstrip('/')}/parecido",
        json={
            'arregloUrl': generate_presigned_url(arrangement, seconds),
            'audioUrls': [generate_presigned_url(key, seconds) for key in item.variant_keys],
        },
        timeout=(settings.TARAREO_HTTP_TIMEOUT_SECONDS, settings.HUMMING_SIMILARITY_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    results = [
        {'puntaje': r.get('puntaje'), 'nivel': r.get('nivel')}
        for r in (response.json().get('resultados') or [])
    ][: len(item.variant_keys)]
    HummingEnhancement.objects.filter(id=enhancement_id).update(
        variant_similarity=results, updated_at=timezone.now()
    )
    return results


def _delete_keys(keys: list[str]) -> None:
    from ml.storage_client import delete_file

    for key in keys:
        try:
            delete_file(key)
        except Exception:
            logger.exception('No se pudo borrar la variante descartada %s', key)


# ── Versiones del tarareo producidas con IA automáticamente ──────────────────

def automatic_enabled() -> bool:
    return bool(settings.HUMMING_AI_VERSIONS and settings.MODAL_ENDPOINT_FROM_REFERENCE)


def start_automatic_versions(job_id: str) -> list[str]:
    """
    Crea (una sola vez) la mejora automática de cada versión del tarareo que ya
    tiene audio y estilo, y la encola. Se llama en cada aviso del worker, así
    la versión 1 se produce con IA mientras el worker arma las alternativas.
    No reserva créditos: el tarareo con IA cuesta lo mismo que antes.
    """
    if not automatic_enabled():
        return []
    creadas = []
    with transaction.atomic():
        job = HummingJob.objects.select_for_update().get(id=job_id)
        if job.status == 'failed':
            return []
        existentes = set(
            job.enhancements.filter(automatic=True).values_list('version_number', flat=True)
        )
        for version in job.versions:
            numero = int(version.get('numero', 0))
            cancion = version.get('cancion') or ''
            preset = version.get('estilo') or ''
            if numero in existentes or cancion not in (job.available_outputs or []):
                continue
            label, tags = WORKER_PRESETS.get(preset, (preset.title() or 'Original', 'instrumental'))
            item = HummingEnhancement.objects.create(
                humming_job=job, user=job.user, version_number=numero, automatic=True,
                style_key=preset or 'auto', style_label=label,
                prompt=build_prompt(tags, job.metadata),
                fidelity=DEFAULT_FIDELITY, ref_audio_strength=FIDELITY_STRENGTH[DEFAULT_FIDELITY],
            )
            creadas.append(str(item.id))

    from apps.humming.tasks import submit_humming_enhancement

    for item_id in creadas:
        transaction.on_commit(lambda item_id=item_id: submit_humming_enhancement.delay(item_id))
    return creadas


def automatic_for(job: HummingJob, number: int) -> HummingEnhancement | None:
    return job.enhancements.filter(automatic=True, version_number=number).first()
