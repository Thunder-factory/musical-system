"""Procesamiento de resultados parciales y finales recibidos del worker."""

from __future__ import annotations

import io
import json
import logging
import posixpath
from urllib.parse import unquote, urlparse

from django.db import transaction
from django.utils import timezone

from apps.humming.models import HummingJob
from apps.humming.services.constants import (
    ERROR_INVALID_INPUT,
    RESERVATION_TYPE,
    WORKER_STATUS_COMPLETED,
    WORKER_STATUS_FAILED,
    WORKER_STATUS_PROCESSING,
)
from apps.humming.services.job_service import mark_failed

logger = logging.getLogger(__name__)


def _output_name(url: str) -> str:
    return posixpath.basename(unquote(urlparse(url).path))


def metadata_from_analysis(analisis: dict) -> dict:
    """Convierte analisis.json del worker al formato de `metadatos` del resultado final."""
    estilo = analisis.get('estilo') or {}
    return {
        'bpm': (analisis.get('analisis') or {}).get('bpm'),
        'tonalidad': (analisis.get('analisis') or {}).get('tonalidad'),
        'acordes': (analisis.get('armonia') or {}).get('acordes'),
        'estilo': estilo.get('preset'),
        'estiloMensaje': estilo.get('mensaje'),
        'estiloAmbiguo': estilo.get('ambiguo'),
        'duracionCancionSegundos': (analisis.get('render') or {}).get('duracionSegundos'),
        'grafico': analisis.get('grafico'),
        'versiones': [
            {
                key: version.get(key)
                for key in ('numero', 'estilo', 'variante', 'cancion', 'puntaje', 'tipo')
            }
            for version in analisis.get('versiones') or []
        ],
        'provisional': True,
    }


def _partial_metadata(job_id: str, data: dict) -> dict | None:
    """Lee analisis.json cuando el worker avisa que ya hay una versión lista."""
    from apps.humming import services as pkg

    if (
        data.get('estado') != WORKER_STATUS_PROCESSING
        or not str(data.get('etapa', '')).startswith('version-')
    ):
        return None
    if 'analisis.json' not in {_output_name(url) for url in data.get('outputUrls') or []}:
        return None
    job = HummingJob.objects.filter(id=job_id).only('output_keys', 'status').first()
    key = (job.output_keys or {}).get('analisis.json') if job and not job.is_terminal else None
    if not key:
        return None
    try:
        buffer = io.BytesIO()
        pkg.download_fileobj(key, buffer)
        return metadata_from_analysis(json.loads(buffer.getvalue().decode('utf-8')))
    except Exception:
        logger.warning('No se pudo leer el análisis parcial del tarareo %s', job_id, exc_info=True)
        return None


def _start_ai(job_id: str) -> None:
    """Produce con IA las versiones ya listas. Si falla, quedan las de FluidSynth."""
    from apps.humming.enhancement import start_automatic_versions

    try:
        start_automatic_versions(job_id)
    except Exception:
        logger.exception('No se pudo iniciar la IA automática del tarareo %s', job_id)


def _confirm_credits(job: HummingJob) -> int:
    from apps.credits.models import CreditReservation
    from apps.humming import services as pkg

    reservation = CreditReservation.objects.filter(
        reference_id=str(job.id),
        reference_type=RESERVATION_TYPE,
    ).first()
    if not reservation:
        return 0
    try:
        pkg.confirm_reservation(str(reservation.id))
    except (ValueError, pkg.InsufficientCreditsError) as exc:
        logger.warning('No se pudo confirmar el cobro del tarareo %s: %s', job.id, exc)
        return 0
    return reservation.amount


def apply_worker_result(job_id: str, data: dict) -> str:
    """
    Aplica un ResultadoJob del worker de forma idempotente.

    Devuelve 'none' | 'poll' | 'retry'.
    """
    worker_status = data.get('estado')
    partial = _partial_metadata(job_id, data)
    with transaction.atomic():
        job = HummingJob.objects.select_for_update().get(id=job_id)
        if job.is_terminal:
            return 'none'

        now = timezone.now()
        job.progress = max(0, min(100, int(data.get('progreso') or 0)))
        job.stage = (data.get('etapa') or '')[:60]
        job.last_heartbeat_at = now

        available = set(job.available_outputs or [])
        for url in data.get('outputUrls') or []:
            name = _output_name(url)
            if name in (job.output_keys or {}):
                available.add(name)
        job.available_outputs = sorted(available)

        if worker_status == WORKER_STATUS_COMPLETED:
            job.status = 'completed'
            job.progress = 100
            job.metadata = data.get('metadatos') or {}
            job.completed_at = now
            job.credits_used = _confirm_credits(job)
            job.save()
            transaction.on_commit(lambda: _start_ai(job_id))
            return 'none'

        if worker_status == WORKER_STATUS_FAILED:
            code = data.get('codigoError') or ''
            message = data.get('error') or 'El worker no pudo procesar el tarareo.'
            if code == ERROR_INVALID_INPUT:
                job.metadata = data.get('metadatos') or job.metadata
                job.save()
                mark_failed(job_id, message, code)
                return 'none'
            job.error_message = message
            job.error_code = code
            job.save()
            return 'retry'

        if worker_status == WORKER_STATUS_PROCESSING:
            job.status = 'processing'
            if partial:
                job.metadata = partial
                transaction.on_commit(lambda: _start_ai(job_id))
            job.save()
            return 'poll'

        logger.warning('Estado desconocido del worker para %s: %r', job_id, worker_status)
        job.save()
        return 'poll'
