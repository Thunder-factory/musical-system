"""
Tareas Celery del tarareo.

- dispatch_humming_job: firma URLs y hace POST /procesar. Si el worker está
  lleno (503) reintenta tras Retry-After, sin gastar intentos.
- poll_humming_job: respaldo del callback. Consulta GET /jobs/{id} hasta que el
  job termine; si el worker lo perdió (404, reinicio) lo vuelve a despachar.

El callback (views.HummingCallbackView) es el camino principal: el polling
solo cubre callbacks perdidos o un worker reiniciado.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

DISPATCH_NETWORK_RETRIES = 5


def schedule_poll(job_id: str, attempt: int, countdown: int | None = None) -> None:
    """Programa el polling de un despacho concreto (attempt = dispatch_attempts).

    Si el job se vuelve a despachar, la cadena de polling vieja se detiene sola
    porque su attempt ya no coincide: así nunca hay dos cadenas a la vez.
    """
    poll_humming_job.apply_async(
        args=[job_id, attempt],
        countdown=settings.HUMMING_POLL_INTERVAL_SECONDS if countdown is None else countdown,
    )


def schedule_dispatch(job_id: str, countdown: int = 0) -> None:
    dispatch_humming_job.apply_async(args=[job_id], countdown=countdown)


def retry_or_fail(job_id: str, message: str, code: str = '') -> None:
    """Reintenta el despacho si quedan intentos; si no, marca el job como fallido."""
    from apps.humming.services import mark_failed, requeue_for_retry

    if requeue_for_retry(job_id):
        schedule_dispatch(job_id, countdown=10)
    else:
        mark_failed(job_id, message, code)


def handle_retry_action(job_id: str, action: str, data: dict | None = None) -> None:
    """Si el worker falló con un error transitorio, reintenta o marca fallido."""
    if action == 'retry':
        data = data or {}
        retry_or_fail(
            job_id,
            data.get('error') or 'El worker no pudo procesar el tarareo.',
            data.get('codigoError') or '',
        )


def _seconds_since(moment) -> float:
    return (timezone.now() - moment).total_seconds() if moment else 0.0


@shared_task(bind=True, max_retries=DISPATCH_NETWORK_RETRIES)
def dispatch_humming_job(self, job_id: str):
    from apps.humming.models import HummingJob
    from apps.humming.services import (
        WorkerRejectedError,
        WorkerUnavailableError,
        build_dispatch_payload,
        mark_dispatched,
        mark_failed,
        send_to_worker,
    )

    job = HummingJob.objects.filter(id=job_id).first()
    if not job or job.status != 'queued':
        return

    if _seconds_since(job.created_at) > settings.HUMMING_QUEUE_STALE_SECONDS:
        mark_failed(job_id, 'El worker de tarareo no estuvo disponible a tiempo.', 'COLA_VENCIDA')
        return

    try:
        payload, keys = build_dispatch_payload(job)
        outcome = send_to_worker(payload)
    except WorkerRejectedError as exc:
        logger.error('El worker rechazó el tarareo %s: %s', job_id, exc)
        mark_failed(job_id, 'No se pudo enviar el tarareo al procesador.', 'SOLICITUD_INVALIDA')
        return
    except WorkerUnavailableError as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        mark_failed(job_id, 'El worker de tarareo no está disponible.', 'WORKER_NO_DISPONIBLE')
        return

    if not outcome.accepted:
        # Lleno: esperar lo que pide el worker. No consume intentos.
        schedule_dispatch(job_id, countdown=outcome.retry_after)
        return

    attempt = mark_dispatched(job_id, keys)
    if attempt:
        schedule_poll(job_id, attempt)


@shared_task(bind=True, max_retries=10)
def poll_humming_job(self, job_id: str, attempt: int):
    from apps.humming.models import HummingJob
    from apps.humming.services import (
        WorkerUnavailableError,
        apply_worker_result,
        fetch_worker_status,
        mark_failed,
    )

    job = HummingJob.objects.filter(id=job_id).first()
    if not job or job.status != 'processing' or job.dispatch_attempts != attempt:
        return

    if _seconds_since(job.started_at) > settings.HUMMING_PROCESSING_STALE_SECONDS:
        mark_failed(job_id, 'El tarareo excedió el tiempo máximo de procesamiento.', 'TIEMPO_AGOTADO')
        return

    # Si llegó un callback hace poco, no hace falta molestar al worker.
    if job.last_heartbeat_at and (
        _seconds_since(job.last_heartbeat_at) < settings.HUMMING_POLL_INTERVAL_SECONDS / 2
    ):
        schedule_poll(job_id, attempt)
        return

    try:
        data = fetch_worker_status(job_id)
    except WorkerUnavailableError as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=settings.HUMMING_POLL_INTERVAL_SECONDS)
        mark_failed(job_id, 'Se perdió el contacto con el worker de tarareo.', 'WORKER_NO_DISPONIBLE')
        return

    if data is None:
        logger.warning('El worker no conoce el tarareo %s; se vuelve a despachar.', job_id)
        retry_or_fail(job_id, 'El worker de tarareo perdió el trabajo.', 'ERROR_INTERNO')
        return

    action = apply_worker_result(job_id, data)
    if action == 'poll':
        schedule_poll(job_id, attempt)
    else:
        handle_retry_action(job_id, action, data)


# ── "Mejorar con IA" (ACE-Step audio2audio en Modal) ─────────────────────────

def schedule_enhancement_poll(enhancement_id: str) -> None:
    poll_humming_enhancement.apply_async(
        args=[enhancement_id], countdown=settings.HUMMING_ENHANCE_POLL_INTERVAL_SECONDS
    )


@shared_task(bind=True, max_retries=3)
def submit_humming_enhancement(self, enhancement_id: str):
    from apps.humming import enhancement as service
    from apps.humming.models import HummingEnhancement
    from ml.modal_client import ModalGenerationError, submit_music_job

    item = HummingEnhancement.objects.select_related('humming_job').filter(id=enhancement_id).first()
    if not item or item.status != 'queued':
        return
    if not settings.MODAL_ENDPOINT_FROM_REFERENCE:
        # Se encoló con el endpoint configurado y después se quitó: sin esto
        # quedaría "en cola" para siempre y bloquearía elegir esa versión.
        service.mark_failed(enhancement_id, 'La mejora con IA no está disponible por ahora.')
        return
    try:
        response = submit_music_job(
            settings.MODAL_ENDPOINT_FROM_REFERENCE, service.build_modal_body(item)
        )
    except ModalGenerationError as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        service.mark_failed(enhancement_id, 'No se pudo enviar el tarareo a la IA.')
        return
    except Exception:
        # URL inválida, respuesta que no es JSON, etc.: reintentar no lo arregla.
        logger.exception('No se pudo enviar la mejora %s a Modal', enhancement_id)
        service.mark_failed(enhancement_id, 'No se pudo enviar el tarareo a la IA.')
        return

    service.mark_submitted(enhancement_id, response['remote_job_id'])
    schedule_enhancement_poll(enhancement_id)


@shared_task(bind=True, max_retries=10)
def poll_humming_enhancement(self, enhancement_id: str):
    import requests

    from apps.humming import enhancement as service
    from apps.humming.models import HummingEnhancement
    from ml.modal_client import ModalGenerationError, get_music_job_status

    item = HummingEnhancement.objects.filter(id=enhancement_id).first()
    if not item or item.status != 'processing':
        return
    if _seconds_since(item.started_at) > settings.HUMMING_ENHANCE_STALE_SECONDS:
        service.mark_failed(enhancement_id, 'La mejora con IA excedió el tiempo máximo.')
        return

    try:
        remote = get_music_job_status(settings.MODAL_ENDPOINT_FROM_REFERENCE, item.remote_job_id)
    except (ModalGenerationError, ValueError, requests.RequestException) as exc:
        # ValueError: Modal respondió algo que no es JSON (p. ej. una página de error).
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=settings.HUMMING_ENHANCE_POLL_INTERVAL_SECONDS)
        service.mark_failed(enhancement_id, 'Se perdió el contacto con la IA.')
        return

    remote_status = remote.get('status')
    if remote_status in {'queued', 'processing'}:
        progress = max(10, min(95, int(remote.get('progress_pct') or 0)))
        HummingEnhancement.objects.filter(id=enhancement_id, status='processing').update(
            progress=progress, updated_at=timezone.now()
        )
        schedule_enhancement_poll(enhancement_id)
    elif remote_status == 'completed':
        try:
            service.complete(enhancement_id, remote)
        except Exception:
            logger.exception('No se pudo finalizar la mejora %s', enhancement_id)
            service.mark_failed(enhancement_id, 'La IA terminó pero no se pudo guardar la canción.')
    else:
        service.mark_failed(
            enhancement_id, remote.get('error_message') or 'La IA no pudo producir la canción.'
        )


@shared_task(bind=True, max_retries=2, ignore_result=True)
def measure_humming_similarity(self, enhancement_id: str):
    """% de la melodía del tarareo que suena en cada versión con IA (worker /parecido)."""
    import requests

    from apps.humming.enhancement import measure_similarity

    try:
        measure_similarity(enhancement_id)
    except requests.RequestException as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=15)
        logger.warning('No se pudo medir el parecido de la mejora %s: %s', enhancement_id, exc)
    except Exception:
        logger.exception('No se pudo medir el parecido de la mejora %s', enhancement_id)


@shared_task(ignore_result=True)
def warm_ai_gpu():
    """
    Pide a Modal que encienda CoverServer mientras el worker analiza el tarareo.
    Es una optimización: si falla, todo sigue igual (solo se pierde el ahorro).
    """
    import requests

    from apps.humming.enhancement import automatic_enabled

    if not (automatic_enabled() and settings.MODAL_ENDPOINT_WARM_COVER):
        return
    try:
        requests.post(
            settings.MODAL_ENDPOINT_WARM_COVER, json={}, timeout=(5, 15),
            headers={'Modal-Key': settings.MODAL_KEY, 'Modal-Secret': settings.MODAL_SECRET},
        ).raise_for_status()
    except requests.RequestException as exc:
        logger.warning('No se pudo precalentar la GPU de la IA: %s', exc)
