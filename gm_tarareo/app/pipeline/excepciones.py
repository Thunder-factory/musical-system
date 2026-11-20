"""
Excepciones del pipeline.

Cualquier etapa que no pueda seguir levanta una de estas en vez de dejar
propagar el error crudo de la librería subyacente (ffmpeg, basic-pitch,
etc.). main.py las atrapa en un solo lugar para pasar del job a FALLIDO con
un mensaje accionable, tal como pide la restricción 6 de CLAUDE.md.
"""

from __future__ import annotations

from app.modelos import CodigoError, MotivoFallo


class ErrorPipeline(Exception):
    """
    Base de cualquier error que deba terminar el job en FALLIDO.

    `codigo` le dice a Django si conviene reintentar (decisión 8 de
    docs/ARQUITECTURA.md): ERROR_INTERNO es transitorio (red, servidor) y se
    reintenta; ENTRADA_INVALIDA es definitivo (el audio no sirve) y no.
    Por defecto es interno: ante la duda, que Django reintente.
    """

    codigo_por_defecto = CodigoError.ERROR_INTERNO

    def __init__(self, mensaje: str, codigo: CodigoError | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo or self.codigo_por_defecto


class ErrorIngesta(ErrorPipeline):
    """
    El archivo de entrada no se pudo obtener o convertir.

    Archivo corrupto, formato no soportado o demasiado grande → definitivo
    (ENTRADA_INVALIDA, el código por defecto). Una descarga que falla por red
    o por una URL vencida → se marca ERROR_INTERNO al lanzarla: Django puede
    generar URLs nuevas y reintentar.
    """

    codigo_por_defecto = CodigoError.ENTRADA_INVALIDA


class ErrorAlmacenamiento(ErrorPipeline):
    """No se pudieron subir las salidas a R2 (red, URL vencida). Transitorio: se reintenta."""


class ErrorRender(ErrorPipeline):
    """
    No se pudo producir el audio final (falta FluidSynth o el SoundFont, o
    falló el render). Es un problema del servidor, no del tarareo: el mensaje
    lo dice así para no culpar al usuario.
    """


class ErrorAudioInvalido(ErrorPipeline):
    """
    La señal no sirve para extraer una melodía.

    Lleva el `motivo` estructurado (MotivoFallo) además del mensaje, para
    que quede trazado en el callback/metadatos y no solo en texto libre.
    """

    codigo_por_defecto = CodigoError.ENTRADA_INVALIDA

    def __init__(self, motivo: MotivoFallo, mensaje: str) -> None:
        super().__init__(mensaje)
        self.motivo = motivo
