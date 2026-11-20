"""Errores del worker, clasificados como en el contrato."""


class ErrorWorker(Exception):
    codigo = "ERROR_INTERNO"


class EntradaInvalida(ErrorWorker):
    """El video o los parámetros no cumplen las validaciones (culpa de la entrada)."""
    codigo = "ENTRADA_INVALIDA"


class ErrorPipeline(ErrorWorker):
    """Falló una etapa del pipeline (culpa del worker o de su entorno)."""
    codigo = "ERROR_INTERNO"
