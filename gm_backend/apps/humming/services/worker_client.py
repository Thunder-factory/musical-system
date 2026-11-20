"""Cliente HTTP y firma de URLs para comunicarse con el worker gm_tarareo."""

from __future__ import annotations

import requests
from django.conf import settings

from apps.humming.models import HummingJob
from apps.humming.services.constants import (
    CONTRACT_VERSION,
    DispatchOutcome,
    OUTPUT_CONTENT_TYPES,
    WorkerRejectedError,
    WorkerUnavailableError,
    output_key,
)


def _presigned_put(key: str, content_type: str, expires: int) -> str:
    from apps.humming import services as pkg

    return pkg.get_storage_client().generate_presigned_url(
        'put_object',
        Params={'Bucket': pkg.get_storage_bucket(), 'Key': key, 'ContentType': content_type},
        ExpiresIn=expires,
    )


def build_dispatch_payload(job: HummingJob) -> tuple[dict, dict[str, str]]:
    """Firma las URLs de R2 y arma el cuerpo de POST /procesar."""
    from apps.humming import services as pkg

    expires = settings.HUMMING_PRESIGNED_URL_SECONDS
    keys = {name: output_key(job, name) for name in OUTPUT_CONTENT_TYPES}
    payload = {
        'jobId': str(job.id),
        'version': CONTRACT_VERSION,
        'operacion': 'generar',
        'parametros': {},
        'inputUrls': [pkg.generate_presigned_url(job.input_s3_key, expires)],
        'outputUploadUrls': {
            name: _presigned_put(keys[name], content_type, expires)
            for name, content_type in OUTPUT_CONTENT_TYPES.items()
        },
        'callbackUrl': settings.TARAREO_CALLBACK_URL,
    }
    return payload, keys


def send_to_worker(payload: dict) -> DispatchOutcome:
    from apps.humming import services as pkg

    url = f"{settings.TARAREO_URL.rstrip('/')}/procesar"
    try:
        response = pkg.requests.post(
            url, json=payload, timeout=settings.TARAREO_HTTP_TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise WorkerUnavailableError(
            f'No se pudo conectar con el worker de tarareo: {exc}'
        ) from exc

    if response.status_code == 202:
        return DispatchOutcome(accepted=True)
    if response.status_code == 503:
        try:
            retry_after = int(response.headers.get('Retry-After', '30'))
        except ValueError:
            retry_after = 30
        return DispatchOutcome(accepted=False, retry_after=max(5, min(retry_after, 300)))
    if response.status_code == 422:
        raise WorkerRejectedError(f'El worker rechazó la solicitud: {response.text[:500]}')
    raise WorkerUnavailableError(
        f'Respuesta inesperada del worker ({response.status_code}): {response.text[:200]}'
    )


def fetch_worker_status(job_id: str) -> dict | None:
    """GET /jobs/{id}. None si el worker no conoce el job (p. ej. se reinició)."""
    from apps.humming import services as pkg

    url = f"{settings.TARAREO_URL.rstrip('/')}/jobs/{job_id}"
    try:
        response = pkg.requests.get(url, timeout=settings.TARAREO_HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise WorkerUnavailableError(
            f'No se pudo consultar el worker de tarareo: {exc}'
        ) from exc
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise WorkerUnavailableError(
            f'Respuesta inesperada del worker ({response.status_code}) al consultar el job.'
        )
    return response.json()
