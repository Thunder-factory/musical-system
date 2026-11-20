"""Identidad y caché local de las versiones completas de un tarareo de la demo.

En producción Django conserva la relación tarareo/versión/objeto R2. El
worker recibe el analisis.json firmado para completar sin repetir la IA.
"""

import hashlib
import json
from uuid import UUID, uuid5

from app.modelos import AnalisisMelodia


def identificador_version(origen: UUID, numero: int, config) -> UUID:
    ajustes = {n: str(v) for n, v in config.model_dump().items()
               if n.startswith(("render_", "arreglo_", "expresion_")) or n in ("soundfont", "melodia_expresiva")}
    huella = hashlib.sha256(json.dumps(ajustes, sort_keys=True).encode()).hexdigest()[:16]
    return uuid5(origen, f"completa-v5:{numero}:{huella}")


def analisis_guardado(origen: UUID, config) -> AnalisisMelodia:
    return AnalisisMelodia.model_validate_json((config.directorio_job(origen) / "analisis.json").read_text("utf-8"))


def completa_guardada(job_id: UUID, numero: int, config) -> bool:
    carpeta = config.directorio_job(job_id)
    nombre = "cancion.mp3" if numero == 1 else f"cancion-{numero}.mp3"
    return (carpeta / "analisis.json").is_file() and (carpeta / nombre).is_file()
