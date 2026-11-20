"""
Genera los JSON Schema del contrato worker ↔ Django en contratos/vN/.

Los esquemas salen de los modelos Pydantic (la única fuente de verdad), así
que nunca se escriben a mano. El equipo de Django los usa para validar lo que
manda y lo que recibe; tests/test_contrato.py falla si alguien cambia un
modelo sin regenerarlos.

    python -m app.contrato
"""

from __future__ import annotations

import json
from pathlib import Path

from app.modelos import (
    VERSION_CONTRATO,
    RespuestaProcesar,
    RespuestaSalud,
    ResultadoJob,
    SolicitudProcesar,
)

ESQUEMAS = {
    "solicitud_procesar.schema.json": SolicitudProcesar,  # POST /procesar (cuerpo)
    "respuesta_procesar.schema.json": RespuestaProcesar,  # 202 de POST /procesar
    "resultado_job.schema.json": ResultadoJob,  # GET /jobs/{id} y cuerpo del callback
    "salud.schema.json": RespuestaSalud,  # GET /salud
}


def directorio_contrato(raiz: Path | None = None) -> Path:
    raiz = raiz or Path(__file__).resolve().parent.parent
    return raiz / "contratos" / f"v{VERSION_CONTRATO}"


def generar() -> dict[str, str]:
    """Nombre de archivo → contenido JSON (formateado y estable)."""
    return {
        nombre: json.dumps(modelo.model_json_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        for nombre, modelo in ESQUEMAS.items()
    }


def escribir(raiz: Path | None = None) -> list[Path]:
    destino = directorio_contrato(raiz)
    destino.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, contenido in generar().items():
        ruta = destino / nombre
        ruta.write_text(contenido, encoding="utf-8")
        rutas.append(ruta)
    return rutas


if __name__ == "__main__":
    for ruta in escribir():
        print(f"escrito {ruta}")
