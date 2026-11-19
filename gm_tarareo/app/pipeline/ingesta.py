"""
Etapa 1 del pipeline: INGESTA.

Convierte cualquier formato que produzca el navegador o el móvil
(webm/opus, m4a/aac, mp3, wav, lo que sea que entienda ffmpeg) a un WAV
mono a la frecuencia de muestreo que espera basic-pitch más adelante.

Es la puerta de entrada de todo el pipeline: si esto falla, ninguna etapa
siguiente tiene sentido, así que acá se valida agresivamente en vez de
dejar que el error crudo de ffmpeg se propague sin contexto.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.modelos import CodigoError
from app.pipeline.excepciones import ErrorIngesta

logger = logging.getLogger(__name__)

NOMBRE_AUDIO_NORMALIZADO = "audio_normalizado.wav"


def convertir_a_wav(ruta_entrada: Path, ruta_salida: Path, frecuencia_muestreo: int) -> None:
    """
    Invoca ffmpeg para producir un WAV mono a `frecuencia_muestreo` Hz.

    -vn descarta cualquier pista de video (por si alguien graba con la
    cámara activa por error). -ac 1 fuerza mono porque basic-pitch y
    librosa esperan una sola pista de audio.
    """
    comando = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-i", str(ruta_entrada),
        "-vn",
        "-ac", "1",
        "-ar", str(frecuencia_muestreo),
        str(ruta_salida),
    ]

    logger.info("Convirtiendo %s a WAV (%d Hz, mono)", ruta_entrada.name, frecuencia_muestreo)

    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
    except FileNotFoundError as exc:
        raise ErrorIngesta(
            "ffmpeg no está instalado o no está en el PATH del sistema.", CodigoError.ERROR_INTERNO
        ) from exc

    if resultado.returncode != 0:
        detalle = resultado.stderr.strip().splitlines()[-1] if resultado.stderr.strip() else "sin detalle"
        raise ErrorIngesta(
            f"No se pudo convertir '{ruta_entrada.name}' a WAV. "
            f"¿Es un archivo de audio válido? Detalle de ffmpeg: {detalle}"
        )

    if not ruta_salida.exists() or ruta_salida.stat().st_size == 0:
        raise ErrorIngesta(
            f"ffmpeg terminó sin error pero no generó un WAV válido para '{ruta_entrada.name}'."
        )


NOMBRE_ENTRADA_DESCARGADA = "entrada"


def describir_url(referencia: str) -> str:
    """
    Versión de la URL apta para logs y mensajes de error: sin query string.

    Una URL prefirmada de R2 lleva la firma en la query
    (`X-Amz-Signature=...`). Quien la tiene puede descargar el archivo
    hasta que venza, así que no debe terminar en logs ni en el campo
    `error` que el worker le devuelve al backend.
    """
    return referencia.split("?", 1)[0]


def _extension_segura(referencia: str) -> str:
    """
    Extensión del archivo remoto, solo si es alfanumérica y corta.

    El archivo descargado siempre se guarda como `entrada<ext>` dentro de la
    carpeta del job: el nombre que viene en la URL no se usa tal cual
    porque `Path("..").name` es `".."`. La extensión es solo informativa:
    ffmpeg detecta el formato real por el contenido, no por el nombre.
    """
    sufijo = Path(describir_url(referencia)).suffix
    return sufijo if sufijo[1:].isalnum() and len(sufijo) <= 6 else ""


def _descargar(referencia: str, destino: Path, tamano_maximo: int, timeout: float) -> None:
    """
    Descarga por streaming cortando si supera `tamano_maximo` bytes.

    Se revisa Content-Length antes de bajar nada (rechazo inmediato), y
    también se cuentan los bytes mientras llegan, porque el header puede
    faltar o mentir.
    """
    import httpx

    url_visible = describir_url(referencia)
    mensaje_grande = (
        f"El audio de entrada supera el máximo de {tamano_maximo // (1024 * 1024)} MB. "
        "Una grabación de 30 s no debería pesar tanto: revisá que sea el archivo correcto."
    )
    try:
        with httpx.stream("GET", referencia, timeout=timeout) as respuesta:
            respuesta.raise_for_status()
            declarado = respuesta.headers.get("content-length")
            if declarado and declarado.isdigit() and int(declarado) > tamano_maximo:
                raise ErrorIngesta(mensaje_grande)

            recibidos = 0
            with open(destino, "wb") as archivo:
                for bloque in respuesta.iter_bytes():
                    recibidos += len(bloque)
                    if recibidos > tamano_maximo:
                        raise ErrorIngesta(mensaje_grande)
                    archivo.write(bloque)
    except httpx.HTTPStatusError as exc:
        destino.unlink(missing_ok=True)
        raise ErrorIngesta(
            f"No se pudo descargar el audio de entrada desde {url_visible}: "
            f"el servidor respondió {exc.response.status_code}. "
            "Si es una URL prefirmada, puede haber vencido.",
            CodigoError.ERROR_INTERNO,
        ) from exc
    except httpx.HTTPError as exc:
        destino.unlink(missing_ok=True)
        raise ErrorIngesta(
            f"No se pudo descargar el audio de entrada desde {url_visible}: {type(exc).__name__}",
            CodigoError.ERROR_INTERNO,
        ) from exc
    except ErrorIngesta:
        destino.unlink(missing_ok=True)
        raise


def obtener_archivo_local(referencia: str, directorio_job: Path, config) -> Path:
    """
    Resuelve una entrada de `inputUrls` a un archivo en disco.

    - http(s)://: se descarga a la carpeta del job. Es el caso de producción:
      una URL prefirmada de GET a Cloudflare R2, generada por Django al
      despachar. El worker no necesita credenciales de R2.
    - file:// o una ruta local: se usa tal cual, **solo con
      TARAREO_MODO_DESARROLLO=true** (probar sin storage). En producción
      se rechaza: si no, cualquiera que pueda llamar al worker podría
      hacerle leer archivos del contenedor.

    En los dos casos se aplica el mismo límite de tamaño, y el resto del
    pipeline siempre recibe una Path local.
    """
    tamano_maximo = config.descarga_tamano_maximo_bytes

    if referencia.startswith(("http://", "https://")):
        directorio_job.mkdir(parents=True, exist_ok=True)
        destino = directorio_job / (NOMBRE_ENTRADA_DESCARGADA + _extension_segura(referencia))
        _descargar(referencia, destino, tamano_maximo, config.descarga_timeout_segundos)
        return destino

    if not config.modo_desarrollo:
        raise ErrorIngesta(
            "La entrada tiene que ser una URL http(s) (por ejemplo, una URL prefirmada de R2). "
            "Las rutas locales y file:// solo se aceptan con TARAREO_MODO_DESARROLLO=true."
        )

    ruta = Path(referencia.removeprefix("file://"))
    if not ruta.is_file():
        raise ErrorIngesta(f"No se encontró el archivo de entrada: {referencia}")
    if ruta.stat().st_size > tamano_maximo:
        raise ErrorIngesta(
            f"El audio de entrada supera el máximo de {tamano_maximo // (1024 * 1024)} MB."
        )
    return ruta


def ingestar(ruta_entrada: Path, directorio_job: Path, frecuencia_muestreo: int) -> Path:
    """
    Punto de entrada de la etapa: valida el archivo de origen, crea la
    carpeta de trabajo del job y devuelve la ruta al WAV normalizado.
    """
    if not ruta_entrada.exists():
        raise ErrorIngesta(f"El archivo de entrada no existe: {ruta_entrada}")
    if ruta_entrada.stat().st_size == 0:
        raise ErrorIngesta(f"El archivo de entrada está vacío: {ruta_entrada.name}")

    directorio_job.mkdir(parents=True, exist_ok=True)
    ruta_salida = directorio_job / NOMBRE_AUDIO_NORMALIZADO

    convertir_a_wav(ruta_entrada, ruta_salida, frecuencia_muestreo)

    logger.info("WAV normalizado listo: %s", ruta_salida)
    return ruta_salida
