"""Busca la letra de una canción en LRCLIB (https://lrclib.net) a partir de título y artista.

Sin GPU y sin clave. La letra solo se usa dentro del worker para corregir a Whisper: no se entrega
ni se muestra (ver app/pipeline/letra.py: letra_publica). Si LRCLIB no responde o no la tiene, el
pipeline sigue con lo que oiga Whisper: nunca es motivo de error.
"""
import logging
import re
import unicodedata

import httpx

from app.config import Config, obtener_config

log = logging.getLogger("worker.lrclib")

_MARCA_TIEMPO = re.compile(r"^\s*(\[\d+:\d+(?:[.:]\d+)?\])+\s*")
_AGENTE = "worker-traduccion/1.0 (proyecto academico; doblaje de videos musicales)"


def _clave(texto: str | None) -> str:
    """Minúsculas, sin acentos ni signos: para comparar títulos y artistas."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"\(.*?\)|\[.*?\]", " ", texto)  # (Remastered), [Official Video]...
    return re.sub(r"[\W_]+", "", texto)


def quitar_marcas_de_tiempo(lrc: str) -> str:
    """Letra sincronizada (.lrc) → texto plano, un verso por línea."""
    return "\n".join(_MARCA_TIEMPO.sub("", l) for l in lrc.splitlines()).strip()


def _texto(candidato: dict) -> str:
    plano = (candidato.get("plainLyrics") or "").strip()
    if plano:
        return plano
    return quitar_marcas_de_tiempo(candidato.get("syncedLyrics") or "")


def elegir_candidato(candidatos: list[dict], titulo: str, artista: str | None,
                     duracion_s: float | None) -> dict | None:
    """El resultado que mejor encaja: mismo título, mismo artista y duración más parecida.

    Se descartan los instrumentales y los que no traen letra. El título tiene que coincidir (o uno
    contener al otro); el artista, si se dio, también. La duración solo desempata: el video puede
    traer intro o estar recortado.
    """
    t, a = _clave(titulo), _clave(artista)
    validos = []
    for c in candidatos:
        if c.get("instrumental") or not _texto(c):
            continue
        ct, ca = _clave(c.get("trackName") or c.get("name")), _clave(c.get("artistName"))
        if not ct or not (ct == t or t in ct or ct in t):
            continue
        if a and not (ca == a or a in ca or ca in a):
            continue
        exacto = (ct == t) + (bool(a) and ca == a)
        dif = abs(float(c.get("duration") or 0) - duracion_s) if duracion_s else 0.0
        validos.append((-exacto, dif, c))
    if not validos:
        return None
    return min(validos, key=lambda v: (v[0], v[1]))[2]


def buscar_letra(titulo: str, artista: str | None = None, duracion_s: float | None = None,
                 cfg: Config | None = None, cliente: httpx.Client | None = None) -> dict | None:
    """→ {texto, id, titulo, artista, duracion_s} o None si no se encuentra (o LRCLIB falla)."""
    cfg = cfg or obtener_config()
    if not cfg.lrclib_activo or not (titulo or "").strip():
        return None
    params = {"track_name": titulo.strip()}
    if artista and artista.strip():
        params["artist_name"] = artista.strip()
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=cfg.lrclib_timeout_s, headers={"User-Agent": _AGENTE})
    try:
        r = cliente.get(f"{cfg.lrclib_url.rstrip('/')}/api/search", params=params)
        r.raise_for_status()
        candidatos = r.json()
    except (httpx.HTTPError, ValueError) as e:
        log.warning("LRCLIB no respondió (%s): se sigue con la transcripción de Whisper", e)
        return None
    finally:
        if propio:
            cliente.close()
    if not isinstance(candidatos, list):
        return None
    elegido = elegir_candidato(candidatos, titulo, artista, duracion_s)
    if not elegido:
        log.info("LRCLIB: sin letra para «%s» de «%s» (%d resultados)", titulo, artista or "?", len(candidatos))
        return None
    log.info("LRCLIB: letra encontrada (id=%s, «%s» de «%s», %.0f s)", elegido.get("id"),
             elegido.get("trackName"), elegido.get("artistName"), float(elegido.get("duration") or 0))
    return {"texto": _texto(elegido), "id": elegido.get("id"), "titulo": elegido.get("trackName"),
            "artista": elegido.get("artistName"), "duracion_s": elegido.get("duration")}
