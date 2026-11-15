"""Cliente central para el almacenamiento compatible con S3 de Cloudflare R2."""

from __future__ import annotations

import os
import uuid
from typing import BinaryIO

import boto3
from django.conf import settings


class StorageConfigurationError(RuntimeError):
    """La configuración necesaria para acceder al bucket no está completa."""


def _storage_settings() -> dict[str, str]:
    values = {
        "endpoint_url": settings.R2_ENDPOINT,
        "region_name": settings.R2_REGION,
        "aws_access_key_id": settings.R2_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.R2_SECRET_ACCESS_KEY,
        "bucket": settings.R2_DOCUMENTS_BUCKET,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise StorageConfigurationError(
            "Faltan variables de configuración R2: "
            + ", ".join(missing)
        )
    return values


def get_storage_client():
    """Crea un cliente boto3 configurado para Cloudflare R2."""
    values = _storage_settings()
    return boto3.client(
        "s3",
        endpoint_url=values["endpoint_url"],
        region_name=values["region_name"],
        aws_access_key_id=values["aws_access_key_id"],
        aws_secret_access_key=values["aws_secret_access_key"],
    )


def get_storage_bucket() -> str:
    """Devuelve el bucket R2 configurado después de validarlo."""
    return _storage_settings()["bucket"]


def upload_fileobj(file_obj: BinaryIO, folder: str = "") -> str:
    """Sube un archivo y devuelve una clave única dentro del bucket R2."""
    file_ext = os.path.splitext(getattr(file_obj, "name", ""))[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    key = f"{folder.rstrip('/')}/{unique_filename}" if folder else unique_filename

    get_storage_client().upload_fileobj(file_obj, get_storage_bucket(), key)
    return key


def upload_file(file_path: str, key: str) -> None:
    """Sube un archivo local a una clave específica del bucket R2."""
    get_storage_client().upload_file(file_path, get_storage_bucket(), key)


def download_file(key: str, file_path: str) -> None:
    """Descarga una clave R2 a una ruta local."""
    get_storage_client().download_file(get_storage_bucket(), key, file_path)


def download_fileobj(key: str, file_obj: BinaryIO) -> None:
    """Descarga una clave R2 en un objeto de archivo abierto."""
    get_storage_client().download_fileobj(get_storage_bucket(), key, file_obj)


def generate_presigned_url(key: str, expiry_seconds: int = 3600) -> str:
    """Genera una URL temporal para leer un objeto privado de R2."""
    return get_storage_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": get_storage_bucket(), "Key": key},
        ExpiresIn=expiry_seconds,
    )


def get_presigned_url(s3_key: str, expiry_seconds: int = 3600) -> str:
    """Nombre compatible con los consumidores actuales del proyecto."""
    return generate_presigned_url(s3_key, expiry_seconds)


def upload_to_s3(file_obj: BinaryIO, folder: str = "") -> str:
    """Nombre compatible con el flujo actual de subida de archivos."""
    return upload_fileobj(file_obj, folder)
