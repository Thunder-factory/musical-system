"""El contrato publicado en contratos/vN/ tiene que coincidir con los modelos."""

import json

from app.contrato import directorio_contrato, generar
from app.modelos import TIPOS_SALIDA


def test_los_esquemas_publicados_estan_al_dia():
    """Si falla: cambió un modelo del contrato. Regenerar con `python -m app.contrato` y avisar al equipo."""
    for nombre, esperado in generar().items():
        ruta = directorio_contrato() / nombre
        assert ruta.is_file(), f"Falta {ruta}: correr `python -m app.contrato`"
        assert ruta.read_text(encoding="utf-8") == esperado, f"{nombre} está desactualizado"


def test_la_solicitud_documenta_las_salidas_y_el_resultado_el_codigo_de_error():
    esquemas = {nombre: json.loads(texto) for nombre, texto in generar().items()}
    solicitud = esquemas["solicitud_procesar.schema.json"]["properties"]
    resultado = esquemas["resultado_job.schema.json"]

    assert "outputUploadUrls" in solicitud and "version" in solicitud
    parametros = esquemas["solicitud_procesar.schema.json"]["$defs"]["ParametrosProcesamiento"]["properties"]
    assert "genero" not in parametros  # el usuario no elige género (se acepta como extra y se ignora)
    assert set(resultado["$defs"]["CodigoError"]["enum"]) == {"ENTRADA_INVALIDA", "ERROR_INTERNO"}
    assert set(TIPOS_SALIDA) == {"cancion.mp3", "melodia.mid", "arreglo.mid", "analisis.json",
                                 "cancion-2.mp3", "arreglo-2.mid", "cancion-3.mp3", "arreglo-3.mid",
                                 "muestra.mp3", "muestra-2.mp3", "muestra-3.mp3", "partitura.musicxml"}
