from __future__ import annotations

import time
import requests
from django.conf import settings

from ml.storage_client import generate_presigned_url, upload_fileobj

_COLD_START_WAIT = 30
_COLD_START_ATTEMPTS = 6


def _timeouts(read_timeout: int):
    return (
        getattr(settings, 'MODAL_CONNECT_TIMEOUT_SECONDS', 10),
        read_timeout,
    )


def _headers():
    return {
        "Content-Type": "application/json",
        "Modal-Key": settings.MODAL_KEY,
        "Modal-Secret": settings.MODAL_SECRET,
    }


def _post_with_retries(endpoint_url: str, body: dict, *, read_timeout: int, attempts: int):
    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.post(
                endpoint_url,
                json=body,
                headers=_headers(),
                timeout=_timeouts(read_timeout),
            )
            if response.status_code == 404 and "is stopped" in response.text:
                if attempt < attempts - 1:
                    time.sleep(_COLD_START_WAIT)
                    continue
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(min(30, 2 ** attempt))
                continue
            raise ModalGenerationError("Modal no respondió dentro del tiempo límite.") from exc
    if last_error:
        raise ModalGenerationError("Modal no respondió.") from last_error
    raise ModalGenerationError("Modal no respondió.")


def call_modal_endpoint(endpoint_url: str, body: dict) -> dict:
    """
    Llama a uno de los endpoints del MusicGenServer desplegado en Modal.
    Si Modal responde 404 "app is stopped" (cold start), reintenta
    automáticamente hasta _COLD_START_ATTEMPTS veces antes de fallar.
    """
    for attempt in range(_COLD_START_ATTEMPTS):
        response = _post_with_retries(
            endpoint_url,
            body,
            read_timeout=getattr(settings, 'MODAL_GENERATION_READ_TIMEOUT_SECONDS', 900),
            attempts=1,
        )

        # Cold start: Modal devuelve 404 mientras el app arranca.
        # Esperamos y reintentamos; el primer request ya disparó el wake-up.
        if response.status_code == 404 and "is stopped" in response.text:
            if attempt < _COLD_START_ATTEMPTS - 1:
                time.sleep(_COLD_START_WAIT)
                continue
            raise ModalGenerationError(
                f"Modal no arrancó tras {_COLD_START_ATTEMPTS} intentos: {response.text[:200]}"
            )

        if not response.ok:
            raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")

        data = response.json()
        if "s3_key" not in data and "stems" not in data:
            raise ModalGenerationError(f"Respuesta inesperada: {data}")
        return data

    raise ModalGenerationError("Modal no respondió.")


def submit_stem_job(endpoint_url: str, body: dict) -> dict:
    """Envía una separación asíncrona y retorna su remote_job_id."""
    payload = {**body, "async": True}
    response = _post_with_retries(
        endpoint_url,
        payload,
        read_timeout=getattr(settings, 'MODAL_SUBMIT_READ_TIMEOUT_SECONDS', 30),
        attempts=getattr(settings, 'MODAL_REQUEST_RETRIES', 3),
    )
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")

    data = response.json()
    if not data.get("remote_job_id"):
        raise ModalGenerationError(f"Respuesta asíncrona inesperada: {data}")
    return data


def get_stem_job_status(endpoint_url: str, remote_job_id: str) -> dict:
    """Consulta el estado de una separación remota sin iniciar otra ejecución."""
    response = _post_with_retries(
        endpoint_url,
        {"action": "status", "remote_job_id": remote_job_id},
        read_timeout=getattr(settings, 'MODAL_STATUS_READ_TIMEOUT_SECONDS', 30),
        attempts=getattr(settings, 'MODAL_REQUEST_RETRIES', 3),
    )
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")

    data = response.json()
    if "status" not in data or "progress_pct" not in data:
        raise ModalGenerationError(f"Estado remoto inesperado: {data}")
    return data


def submit_faceswap_job(endpoint_url: str, body: dict) -> dict:
    """Envía un face swap asíncrono y retorna su remote_job_id."""
    response = _post_with_retries(
        endpoint_url,
        {**body, "async": True},
        read_timeout=getattr(settings, 'MODAL_SUBMIT_READ_TIMEOUT_SECONDS', 30),
        attempts=getattr(settings, 'MODAL_REQUEST_RETRIES', 3),
    )
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")
    data = response.json()
    if not data.get("remote_job_id"):
        raise ModalGenerationError(f"Respuesta asíncrona inesperada: {data}")
    return data


def get_faceswap_job_status(endpoint_url: str, remote_job_id: str) -> dict:
    """Consulta el estado de un face swap remoto sin iniciar otra ejecución."""
    response = _post_with_retries(
        endpoint_url,
        {"action": "status", "remote_job_id": remote_job_id},
        read_timeout=getattr(settings, 'MODAL_STATUS_READ_TIMEOUT_SECONDS', 30),
        attempts=getattr(settings, 'MODAL_REQUEST_RETRIES', 3),
    )
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")
    data = response.json()
    if "status" not in data or "progress_pct" not in data:
        raise ModalGenerationError(f"Estado remoto inesperado: {data}")
    return data


def submit_music_job(endpoint_url: str, body: dict) -> dict:
    """Envía una generación musical asíncrona y retorna su remote_job_id."""
    response = _post_with_retries(
        endpoint_url,
        {**body, "async": True},
        read_timeout=getattr(settings, 'MODAL_SUBMIT_READ_TIMEOUT_SECONDS', 30),
        attempts=getattr(settings, 'MODAL_REQUEST_RETRIES', 3),
    )
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")
    data = response.json()
    if not data.get("remote_job_id"):
        raise ModalGenerationError(f"Respuesta asíncrona inesperada: {data}")
    return data


def get_music_job_status(endpoint_url: str, remote_job_id: str) -> dict:
    """Consulta el estado de una generación musical remota."""
    response = _post_with_retries(
        endpoint_url,
        {"action": "status", "remote_job_id": remote_job_id},
        read_timeout=getattr(settings, 'MODAL_STATUS_READ_TIMEOUT_SECONDS', 30),
        attempts=getattr(settings, 'MODAL_REQUEST_RETRIES', 3),
    )
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")
    data = response.json()
    if "status" not in data or "progress_pct" not in data:
        raise ModalGenerationError(f"Estado remoto inesperado: {data}")
    return data


def submit_translation_job(endpoint_url: str, body: dict) -> dict:
    """Envía un doblaje asíncrono de video y retorna su remote_job_id."""
    response = _post_with_retries(
        endpoint_url,
        {**body, "async": True},
        read_timeout=getattr(settings, 'MODAL_SUBMIT_READ_TIMEOUT_SECONDS', 30),
        attempts=getattr(settings, 'MODAL_REQUEST_RETRIES', 3),
    )
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")
    data = response.json()
    if data.get("status") == "failed":
        raise ModalGenerationError(
            data.get("error_message") or "La traducción falló en el servidor remoto."
        )
    if not data.get("remote_job_id"):
        raise ModalGenerationError(f"Respuesta asíncrona inesperada: {data}")
    return data


def get_translation_job_status(endpoint_url: str, remote_job_id: str) -> dict:
    """Consulta el estado de un doblaje remoto sin iniciar otra ejecución."""
    response = _post_with_retries(
        endpoint_url,
        {"action": "status", "remote_job_id": remote_job_id},
        read_timeout=getattr(settings, 'MODAL_STATUS_READ_TIMEOUT_SECONDS', 30),
        attempts=getattr(settings, 'MODAL_REQUEST_RETRIES', 3),
    )
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")
    data = response.json()
    if "status" not in data or "progress_pct" not in data:
        raise ModalGenerationError(f"Estado remoto inesperado: {data}")
    return data


def get_presigned_url(s3_key: str, expiry_seconds: int = 3600) -> str:
    """Alias legacy; usar ``ml.storage_client.generate_presigned_url``."""
    return generate_presigned_url(s3_key, expiry_seconds)


class ModalGenerationError(Exception):
    """Se lanza cuando la llamada al servidor Modal falla o retorna datos inesperados."""


def upload_to_s3(file_obj, folder: str = "") -> str:
    """Alias legacy; usar ``ml.storage_client.upload_fileobj``."""
    return upload_fileobj(file_obj, folder)
