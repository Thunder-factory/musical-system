from __future__ import annotations

import time
import requests
from django.conf import settings

from ml.storage_client import generate_presigned_url, upload_fileobj

_COLD_START_WAIT = 30    # segundos entre reintentos mientras Modal arranca
_COLD_START_ATTEMPTS = 6  # máximo ~2.5 min de espera (5 esperas × 30 s)


def call_modal_endpoint(endpoint_url: str, body: dict) -> dict:
    """
    Llama a uno de los endpoints del MusicGenServer desplegado en Modal.
    Si Modal responde 404 "app is stopped" (cold start), reintenta
    automáticamente hasta _COLD_START_ATTEMPTS veces antes de fallar.
    """
    headers = {
        "Content-Type": "application/json",
        "Modal-Key": settings.MODAL_KEY,
        "Modal-Secret": settings.MODAL_SECRET,
    }

    for attempt in range(_COLD_START_ATTEMPTS):
        response = requests.post(
            endpoint_url,
            json=body,
            headers=headers,
            timeout=600,  # ACE-Step puede tardar hasta 5-10 min
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
    headers = {
        "Content-Type": "application/json",
        "Modal-Key": settings.MODAL_KEY,
        "Modal-Secret": settings.MODAL_SECRET,
    }
    payload = {**body, "async": True}
    response = requests.post(endpoint_url, json=payload, headers=headers, timeout=30)
    if not response.ok:
        raise ModalGenerationError(f"Modal {response.status_code}: {response.text[:300]}")

    data = response.json()
    if not data.get("remote_job_id"):
        raise ModalGenerationError(f"Respuesta asíncrona inesperada: {data}")
    return data


def get_stem_job_status(endpoint_url: str, remote_job_id: str) -> dict:
    """Consulta el estado de una separación remota sin iniciar otra ejecución."""
    headers = {
        "Content-Type": "application/json",
        "Modal-Key": settings.MODAL_KEY,
        "Modal-Secret": settings.MODAL_SECRET,
    }
    response = requests.post(
        endpoint_url,
        json={"action": "status", "remote_job_id": remote_job_id},
        headers=headers,
        timeout=30,
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
