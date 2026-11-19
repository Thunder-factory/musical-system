"""Validación de fotos y videos para el cambio de caras (Pillow + ffprobe)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from PIL import Image

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.webm'}
MIN_PHOTO_SIDE_PX = 128
# Tolerancia por redondeo del contenedor; Modal además recorta con -t 15.
DURATION_TOLERANCE_SECONDS = 0.5


class PhotoValidationError(Exception):
    """La foto no es una imagen JPG/PNG/WEBP válida o no cumple los límites."""


class VideoValidationError(Exception):
    """El video no es un MP4/MOV/WEBM decodificable o no cumple los límites."""


def _extension(file: UploadedFile) -> str:
    return os.path.splitext(getattr(file, 'name', '') or '')[1].lower()


def validate_photo(file: UploadedFile, *, max_bytes: int | None = None) -> str:
    """
    Valida extensión, tamaño y contenido de una foto con Pillow.

    Args:
        file: Foto subida por el usuario o el admin.
        max_bytes: Tope en bytes; por defecto ``FACESWAP_MAX_PHOTO_BYTES``.

    Returns:
        La extensión en minúsculas (p. ej. ``.jpg``).

    Raises:
        PhotoValidationError: Si la foto no cumple alguna regla.
    """
    limit = max_bytes if max_bytes is not None else settings.FACESWAP_MAX_PHOTO_BYTES
    extension = _extension(file)
    if extension not in PHOTO_EXTENSIONS:
        raise PhotoValidationError('Solo se aceptan fotos JPG, PNG o WEBP.')
    size = getattr(file, 'size', 0) or 0
    if size <= 0:
        raise PhotoValidationError('La foto está vacía.')
    if size > limit:
        raise PhotoValidationError(
            f'La foto excede el límite de {limit // (1024 * 1024)} MB.'
        )

    try:
        file.seek(0)
        with Image.open(file) as image:
            image.verify()
        # verify() deja la imagen inutilizable: se reabre para leer el tamaño.
        file.seek(0)
        with Image.open(file) as image:
            width, height = image.size
    except Exception as exc:
        raise PhotoValidationError('El archivo no es una imagen válida.') from exc
    finally:
        file.seek(0)

    if min(width, height) < MIN_PHOTO_SIDE_PX:
        raise PhotoValidationError('La foto es muy pequeña (mínimo 128×128 px).')
    return extension


def _probe(path: str) -> dict:
    probe = subprocess.run(
        [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height:format=duration',
            '-of', 'json', path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(probe.stdout or '{}')


def validate_video(file: UploadedFile, *, max_seconds: int) -> float:
    """
    Valida extensión, tamaño, decodificabilidad y duración de un video con ffprobe.

    Args:
        file: Clip subido por el usuario o video de plantilla del admin.
        max_seconds: Duración máxima permitida en segundos.

    Returns:
        La duración del video en segundos.

    Raises:
        VideoValidationError: Si el video no cumple alguna regla.
    """
    extension = _extension(file)
    if extension not in VIDEO_EXTENSIONS:
        raise VideoValidationError('Solo se aceptan videos MP4, MOV o WEBM.')
    size = getattr(file, 'size', 0) or 0
    if size <= 0:
        raise VideoValidationError('El video está vacío.')
    if size > settings.FACESWAP_MAX_VIDEO_BYTES:
        limit_mb = settings.FACESWAP_MAX_VIDEO_BYTES // (1024 * 1024)
        raise VideoValidationError(f'El video excede el límite de {limit_mb} MB.')

    with tempfile.NamedTemporaryFile(suffix=extension) as temporary:
        file.seek(0)
        for chunk in file.chunks():
            temporary.write(chunk)
        temporary.flush()
        file.seek(0)
        try:
            data = _probe(temporary.name)
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
            raise VideoValidationError('El archivo no contiene video decodificable.') from exc

    if not data.get('streams'):
        raise VideoValidationError('El archivo no contiene video decodificable.')
    try:
        duration = float((data.get('format') or {}).get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise VideoValidationError('No se pudo determinar la duración del video.')
    if duration > max_seconds + DURATION_TOLERANCE_SECONDS:
        raise VideoValidationError(
            f'El video debe durar como máximo {max_seconds} segundos.'
        )
    file.seek(0)
    return duration


def extract_thumbnail(video_path: str | Path, at_s: float) -> Path:
    """
    Extrae un fotograma JPG de 360 px de alto en el segundo indicado.

    Args:
        video_path: Ruta local del video.
        at_s: Segundo del fotograma.

    Returns:
        Ruta de un JPG temporal; quien llama debe borrarlo.

    Raises:
        VideoValidationError: Si ffmpeg no pudo generar la miniatura.
    """
    handle, out_path = tempfile.mkstemp(suffix='.jpg')
    os.close(handle)
    try:
        subprocess.run(
            [
                'ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0.0, at_s):.3f}',
                '-i', str(video_path), '-frames:v', '1', '-vf', 'scale=-2:360', out_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        os.unlink(out_path)
        raise VideoValidationError('No se pudo generar la miniatura del video.') from exc
    if os.path.getsize(out_path) <= 0:
        os.unlink(out_path)
        raise VideoValidationError('No se pudo generar la miniatura del video.')
    return Path(out_path)
