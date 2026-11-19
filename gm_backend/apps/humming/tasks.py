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
