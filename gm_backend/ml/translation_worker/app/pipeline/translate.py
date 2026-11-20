"""Etapa 4 — traducir y adaptar la letra a la métrica con un LLM.

El LLM va detrás de la interfaz `Traductor`. En MusicAI (Modal) se usa Gemini (LLM_PROVEEDOR=gemini);
la implementación de Ollama se conserva del worker original de SW1 para ejecutarlo en local.
Con Ollama, el modelo se elige de un catálogo por niveles (alto / medio / ligero) según la VRAM libre.
"""
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.config import Config, NivelLlm, obtener_config
from app.errores import ErrorPipeline
from app.gpu import info_gpu

log = logging.getLogger("worker.traducir")

NOMBRES_IDIOMA = {"en": "English", "es": "Spanish", "fr": "French", "zh": "Simplified Chinese",
                  "pt": "Portuguese", "it": "Italian", "de": "German", "ja": "Japanese", "ko": "Korean"}
TAMANO_LOTE = 25
RESUMEN_MAX_PALABRAS = 110  # se piden 70: bastante más ya no es un resumen
_VOCALES = re.compile(r"[aeiouyáéíóúüàèìòùâêîôûäëïöœæ]+", re.IGNORECASE)
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


# ---------- Métrica ----------

def contar_silabas(texto: str, idioma: str = "") -> int:
    """Conteo aproximado: grupos de vocales por palabra; en chino/japonés, un carácter = una sílaba."""
    cjk = len(_CJK.findall(texto))
    total = cjk
    for palabra in re.findall(r"[^\W\d_]+", _CJK.sub(" ", texto)):
        grupos = len(_VOCALES.findall(palabra))
        if idioma in ("en", "fr") and grupos > 1 and palabra.lower().endswith("e"):
            grupos -= 1  # 'e' final muda
        total += max(1, grupos)
    return max(1, total)


# ---------- Oraciones: se traduce por frases completas y luego se reparte entre los versos ----------

_FIN_ORACION = (".", "?", "!", "。", "？", "！")
_PAUSA = (",", ";", ":", "，", "、", "；")
# palabras que nunca cierran una frase: si un verso acaba así, sigue en el siguiente
_COLGANTES = {
    "en": "the a an of to from in on with and or but my your his her our their for through that",
    "es": "el la los las un una de del al a en con y o pero que mi tu su por para sin",
    "fr": "le la les un une de du des à au en avec et ou mais que mon ton son pour sans",
}


def agrupar_en_oraciones(frases: list[dict], idioma: str = "", hueco_max_s: float = 0.7,
                         max_versos: int = 3, max_s: float = 12.0) -> list[list[int]]:
    """Índices de los versos agrupados en frases completas.

    Un verso se une al anterior si va pegado en el tiempo y el anterior queda abierto: acaba en coma
    o en una palabra que no puede cerrar frase, o el siguiente empieza en minúscula.
    Los versos marcados `conservar` (interjecciones) no se traducen y cortan el grupo.
    """
    colgantes = set(_COLGANTES.get(idioma, "").split())
    grupos: list[list[int]] = []
    for i, f in enumerate(frases):
        if f.get("conservar"):
            continue
        if grupos and grupos[-1][-1] == i - 1 and len(grupos[-1]) < max_versos:
            previa = frases[i - 1]
            texto = previa["texto"].rstrip()
            ultima = re.sub(r"[\W_]+$", "", texto.split()[-1].lower()) if texto.split() else ""
            abierto = (texto.endswith(_PAUSA) or f["texto"].lstrip()[:1].islower()
                       or (ultima in colgantes and not texto.endswith(_FIN_ORACION)))
            if (abierto and not texto.endswith(_FIN_ORACION)
                    and f["inicio"] - previa["fin"] <= hueco_max_s
                    and f["fin"] - frases[grupos[-1][0]]["inicio"] <= max_s):
                grupos[-1].append(i)
                continue
        grupos.append([i])
    return grupos


def repartir_texto(texto: str, pesos: list[float], idioma: str = "") -> list[str]:
    """Parte una frase traducida en len(pesos) trozos, con sílabas proporcionales a cada peso
    (la duración de cada verso). Prefiere cortar donde hay una coma."""
    k = len(pesos)
    if k <= 1:
        return [texto.strip()]
    con_espacios = " " in texto.strip() or not _CJK.search(texto)
    piezas = texto.split() if con_espacios else list(texto.strip())
    union = " " if con_espacios else ""
    if len(piezas) <= k:
        return [piezas[i] if i < len(piezas) else "" for i in range(k)]
    acumulado = [0]
    for p in piezas:
        acumulado.append(acumulado[-1] + contar_silabas(p, idioma))
    total_peso = sum(pesos) or 1.0
    cortes, hecho = [0], 0.0
    for b in range(1, k):
        hecho += pesos[b - 1]
        objetivo = acumulado[-1] * hecho / total_peso
        candidatos = range(cortes[-1] + 1, len(piezas) - (k - b) + 1)
        cortes.append(min(candidatos, key=lambda c: abs(acumulado[c] - objetivo)
                          - (1.5 if piezas[c - 1].endswith(_PAUSA + _FIN_ORACION) else 0.0)))
    cortes.append(len(piezas))
    return [union.join(piezas[a:b]) for a, b in zip(cortes, cortes[1:])]


# ---------- Selección del modelo ----------

def motivo_no_disponible(n: NivelLlm, vram_libre_mb: int, instalados: list[str]) -> str | None:
    """Por qué no se puede usar ese nivel ahora mismo; None si está instalado y cabe."""
    if n.modelo not in instalados:
        return f"el modelo {n.modelo} no está instalado"
    if n.vram_min_mb > vram_libre_mb:
        return f"necesita unos {n.vram_min_mb} MB de VRAM y ahora hay {vram_libre_mb} MB disponibles"
    return None


def resolver_nivel(catalogo: list[NivelLlm], nivel: str, vram_libre_mb: int,
                   instalados: list[str]) -> tuple[NivelLlm, str | None]:
    """Elige el modelo del catálogo → (nivel elegido, motivo si no es el que se pidió o no cabe).

    auto → el primero (más alto) que esté instalado y quepa en la VRAM libre.
    nivel fijo → ese; si no está instalado o no cabe, baja al siguiente que cumpla.
    Si ninguno cabe, usa el más ligero instalado (Ollama reparte entre GPU y CPU: va más lento).
    """
    if not catalogo:
        raise ErrorPipeline("el catálogo LLM_NIVELES está vacío")
    nombres = [n.nombre for n in catalogo]
    if nivel != "auto" and nivel not in nombres:
        raise ErrorPipeline(f"LLM_NIVEL={nivel} no existe (válidos: auto, {', '.join(nombres)})")
    candidatos = catalogo if nivel == "auto" else catalogo[nombres.index(nivel):]
    pega = None if nivel == "auto" else motivo_no_disponible(candidatos[0], vram_libre_mb, instalados)
    for n in candidatos:
        if motivo_no_disponible(n, vram_libre_mb, instalados) is None:
            motivo = None
            if nivel not in ("auto", n.nombre):
                motivo = f"nivel '{nivel}' no disponible ({pega}): se usa '{n.nombre}' ({n.modelo})"
                log.warning(motivo)
            return n, motivo
    disponibles = [n for n in catalogo if n.modelo in instalados]
    if not disponibles:
        raise ErrorPipeline("ningún modelo del catálogo está instalado en Ollama "
                            f"({', '.join(n.modelo for n in catalogo)})")
    elegido = disponibles[-1]
    if elegido.vram_min_mb > vram_libre_mb:
        motivo = (f"ningún nivel cabe en {vram_libre_mb} MB disponibles: se usa '{elegido.nombre}' "
                  f"({elegido.modelo}) repartido con la CPU")
    else:  # se pidió un nivel que no está instalado y por debajo no hay ninguno
        motivo = f"nivel '{nivel}' no disponible ({pega}): se usa '{elegido.nombre}' ({elegido.modelo})"
    log.warning(motivo)
    return elegido, motivo


def elegir_nivel(catalogo: list[NivelLlm], nivel: str, vram_libre_mb: int,
                 instalados: list[str]) -> NivelLlm:
    """Como `resolver_nivel`, sin el motivo."""
    return resolver_nivel(catalogo, nivel, vram_libre_mb, instalados)[0]


def vram_disponible_mb(cfg: Config) -> int:
    """VRAM que el LLM puede ocupar: la libre, sin que el total de la tarjeta pase de VRAM_LIMITE_MB."""
    gpu = info_gpu()
    return max(0, min(gpu["vram_libre_mb"], cfg.vram_limite_mb - gpu["vram_usada_mb"]))


# ---------- Interfaz e implementación ----------

class Traductor(ABC):
    """Cualquier LLM (local o API externa opcional) que adapte lotes de versos."""
    nombre: str = "?"
    nivel: str | None = None          # nivel del catálogo realmente usado
    nivel_pedido: str | None = None   # el que se pidió (auto, alto, medio, ligero...)
    motivo_nivel: str | None = None   # por qué se usó otro, si pasó

    @abstractmethod
    def traducir_lote(self, lineas: list[dict], origen: str, destino: str,
                      contexto: str = "", resumen: str = "") -> dict[int, str]:
        """lineas: [{n, texto, silabas, segundos}] → {n: texto adaptado}.

        `contexto` es la letra completa y `resumen` de qué trata la canción y su tono, para que el
        modelo entienda cada frase dentro de la canción.
        Una línea puede traer `aviso`: lo que falló en el intento anterior (p. ej. se pasó de sílabas).
        """

    def resumir(self, letra: str, origen: str) -> str:
        """De qué trata la canción y qué tono tiene (se incluye en cada tanda). '' si no se sabe."""
        return ""

    def revisar_lote(self, lineas: list[dict], destino: str, resumen: str = "") -> dict[int, str]:
        """Segunda pasada: lineas [{n, original, texto, silabas}] → {n: texto corregido}.

        Solo gramática, concordancia y naturalidad; sin cambiar el sentido ni alargar. {} = sin cambios.
        """
        return {}

    def variar(self, intento: int) -> None:
        """Con semilla fija, repetir la misma petición daría lo mismo: cada reintento usa otra."""

    def liberar(self) -> None:
        """Descarga el modelo de la GPU (si aplica)."""


# Ejemplos de adaptación por idioma de destino: (frase original, mal = literal, bien = natural)
EJEMPLOS = {
    "es": [("I'm falling for you", "Estoy cayendo por ti", "Me estoy enamorando"),
           ("I was lost for so long", "Fui perdido por tanto tiempo", "Anduve perdido tanto tiempo"),
           ("You tore me apart", "Me rasgaste aparte", "Me hiciste pedazos"),
           ("I'm on fire tonight", "Estoy en fuego esta noche", "Esta noche estoy que ardo")],
    "en": [("Me haces falta", "You make me lack", "I miss you"),
           ("Tengo ganas de ti", "I have desire of you", "I want you so bad"),
           ("Me vuelves loco", "You return me crazy", "You drive me wild"),
           ("Se me parte el alma", "My soul splits itself", "It tears me apart")],
    "fr": [("I miss you", "Je te manque", "Tu me manques"),
           ("You tore me apart", "Tu m'as déchiré à part", "Tu m'as mis en miettes"),
           ("Hold on tight", "Tiens serré", "Accroche-toi"),
           ("I'm on fire tonight", "Je suis en feu ce soir", "Ce soir je brûle")],
    "zh": [("I'm falling for you", "我正在为你坠落", "我爱上了你"),
           ("You tore me apart", "你把我撕开了", "你让我心碎"),
           ("Hold on tight", "紧紧地握住", "抓紧我"),
           ("I'm on fire tonight", "今晚我着火了", "今夜我热血沸腾")],
}


def _instrucciones(origen: str, destino: str) -> str:
    o, d = NOMBRES_IDIOMA.get(origen, origen), NOMBRES_IDIOMA.get(destino, destino)
    ejemplos = "".join(f'- "{src}" -> bad (literal): "{mal}" | good (natural): "{bien}"\n'
                       for src, mal, bien in EJEMPLOS.get(destino, []))
    return (
        f"You are a professional songwriter who adapts song lyrics from {o} into {d} so they can be sung "
        "over the original melody. This is a song adaptation, NOT a literal translation.\n"
        "You receive a summary of the song, the full lyrics as context, and numbered items to adapt. "
        "Each item is one complete phrase of the song.\n"
        "Rules:\n"
        "1. Return exactly one line per item, with the same number. Never merge, split, skip or reorder items.\n"
        f"2. Natural {d}: write each line the way a native {d} songwriter would say it. Adapt idioms and "
        "expressions instead of translating them word by word; if the literal wording sounds odd, rephrase the idea.\n"
        "3. Keep the meaning, the emotion and the imagery of the original, consistent with the song summary. "
        "Keep the same speaker and verb tense along the song.\n"
        f"4. Flawless {d} grammar: gender and number agreement, right articles and prepositions.\n"
        "5. Singable: never exceed the 'max syllables' of an item. Prefer short, common words; drop filler "
        "and secondary details when needed.\n"
        "6. Rhyme: when it does not hurt the meaning, make the endings of neighbouring lines rhyme or share "
        "assonance (same stressed vowels). Never force a rhyme.\n"
        "7. A phrase that repeats in the song (chorus, hook) must be adapted with exactly the same words every time.\n"
        f"8. Write everything in {d}: never leave a word in {o}, not even a one-word line or a repeated shout. "
        "The lyrics come from automatic transcription: if a word makes no sense, infer what was meant.\n"
        "9. No explanations, no notes, no transliteration, no quotation marks.\n"
        + (f"Examples of adapting a phrase into {d}:\n{ejemplos}" if ejemplos else "")
        + 'Answer only with JSON: {"lineas": [{"n": 1, "texto": "..."}]}'
    )


# Errores típicos que la revisión debe buscar en cada idioma de destino (ejemplos genéricos)
PISTAS_REVISION = {
    "es": "passive calques with 'ser' ('fui nacido' -> 'nací', 'fui perdido' -> 'estuve perdido'); wrong gender or "
          "number ('la problema' -> 'el problema'); a verb or noun that is not the intended word or does not exist; "
          "chains of gerunds copied from English '-ing'; missing or wrong prepositions",
    "en": "calques from the source ('I have 20 years' -> 'I'm 20'); missing subject pronouns; wrong prepositions; "
          "word order copied from the source language",
    "fr": "wrong gender ('le maison' -> 'la maison'); wrong auxiliary ('j'ai allé' -> 'je suis allé'); calques from "
          "English; missing elisions",
    "zh": "word-by-word calques; wrong or missing measure words; unnatural 被 passives; leftover foreign words",
}


def _instrucciones_revision(destino: str) -> str:
    d = NOMBRES_IDIOMA.get(destino, destino)
    pistas = PISTAS_REVISION.get(destino, "")
    return (
        f"You are a strict native {d} editor proofreading the {d} adaptation of a song. For each numbered line you "
        "get the original phrase, the adaptation and its maximum number of syllables.\n"
        "For every line, first write in 'problema' what is wrong with the adaptation ('none' if nothing), then "
        "write the corrected line in 'texto'. Read each line as a native listener would: would anyone really say this?\n"
        "Fix ONLY:\n"
        "- grammar mistakes and wrong gender/number agreement (articles, adjectives, verbs);\n"
        "- wording that no native speaker would say (calques, word-by-word translations), and words that do not "
        "exist or are not the word that was meant;\n"
        f"- words left in another language: write them in {d}.\n"
        + (f"Typical mistakes to look for in {d}: {pistas}.\n" if pistas else "")
        + "Do NOT change the meaning, do not add ideas, do not remove a rhyme, and never make a line longer than "
        "its maximum syllables. If 'problema' is 'none', copy the line exactly as it is.\n"
        'Answer only with JSON: {"lineas": [{"n": 1, "problema": "...", "texto": "..."}]}'
    )


_ESQUEMA_REVISION = {
    "type": "object",
    "properties": {"lineas": {"type": "array", "items": {
        "type": "object",
        "properties": {"n": {"type": "integer"}, "problema": {"type": "string"}, "texto": {"type": "string"}},
        "required": ["n", "problema", "texto"]}}},
    "required": ["lineas"],
}
_ESQUEMA = {
    "type": "object",
    "properties": {"lineas": {"type": "array", "items": {
        "type": "object",
        "properties": {"n": {"type": "integer"}, "texto": {"type": "string"}},
        "required": ["n", "texto"]}}},
    "required": ["lineas"],
}

class TraductorOllama(Traductor):
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.url = cfg.llm_url.rstrip("/")
        if cfg.llm_modelo:
            self.nombre, self.nivel, self.nivel_pedido = cfg.llm_modelo, "fijo", "fijo"
        else:
            # se decide aquí, al llegar a la traducción, con la VRAM que hay en ese momento
            elegido, self.motivo_nivel = resolver_nivel(cfg.catalogo_llm, cfg.llm_nivel,
                                                        vram_disponible_mb(cfg), self.instalados())
            self.nombre, self.nivel, self.nivel_pedido = elegido.modelo, elegido.nombre, cfg.llm_nivel
        log.info("LLM elegido: %s (nivel %s, pedido %s)", self.nombre, self.nivel, self.nivel_pedido)

    def instalados(self) -> list[str]:
        try:
            r = httpx.get(f"{self.url}/api/tags", timeout=10)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except httpx.HTTPError as e:
            raise ErrorPipeline(f"Ollama no responde en {self.url}: {e}") from e

    def variar(self, intento: int) -> None:
        self._intento = intento

    def _chat(self, sistema: str, usuario: str, esquema: dict | None = None, pensar: bool = False) -> str:
        """Una petición a Ollama; devuelve el texto de la respuesta.

        `pensar=True` deja razonar al modelo: Ollama entrega el razonamiento aparte y aquí no se usa.
        """
        cuerpo = {
            "model": self.nombre,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "stream": False,
            "think": pensar,  # por defecto sin razonamiento: más rápido y la salida es solo la respuesta
            "keep_alive": "5m",
            # temperatura baja y semilla fija: la misma letra da la misma traducción en cada corrida
            "options": {"temperature": self.cfg.llm_temperatura, "num_ctx": self.cfg.llm_num_ctx,
                        "seed": self.cfg.llm_semilla + getattr(self, "_intento", 0)},
        }
        if esquema:
            cuerpo["format"] = esquema
        try:
            r = httpx.post(f"{self.url}/api/chat", json=cuerpo, timeout=self.cfg.llm_timeout_s)
            if r.status_code == 400 and "think" in r.text.lower():  # modelo sin modo de razonamiento
                cuerpo.pop("think")
                r = httpx.post(f"{self.url}/api/chat", json=cuerpo, timeout=self.cfg.llm_timeout_s)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ErrorPipeline(f"Ollama falló con {self.nombre}: {e}") from e
        contenido = r.json().get("message", {}).get("content", "")
        return re.sub(r"<think>.*?</think>", "", contenido, flags=re.DOTALL).strip()

    def resumir(self, letra: str, origen: str) -> str:
        o = NOMBRES_IDIOMA.get(origen, origen)
        sistema = (
            f"You analyse song lyrics written in {o} (from automatic transcription, so a few words may be wrong). "
            "Answer in English, in at most 70 words, as plain text with no lists: what the song is about, who is "
            "speaking and to whom, the tone and emotion, and which phrase is the hook that repeats.")
        resumen = " ".join(self._chat(sistema, f"Lyrics:\n{letra}").split())
        if len(resumen.split()) > RESUMEN_MAX_PALABRAS:
            # hay modelos (qwen3:4b) que razonan siempre: sin "think" el razonamiento sale mezclado en la
            # respuesta. Se repite dejándolos razonar, y Ollama lo separa del resumen.
            log.warning("el resumen de %s trae %d palabras (se pidieron 70): parece razonamiento del modelo; "
                        "se repite con el razonamiento aparte", self.nombre, len(resumen.split()))
            resumen = " ".join(self._chat(sistema, f"Lyrics:\n{letra}", pensar=True).split())
            if len(resumen.split()) > RESUMEN_MAX_PALABRAS:
                log.warning("el resumen sigue sin servir: se traduce sin resumen")
                return ""
        return resumen[:700]

    def traducir_lote(self, lineas: list[dict], origen: str, destino: str,
                      contexto: str = "", resumen: str = "") -> dict[int, str]:
        entrada = "\n".join(
            f'{l["n"]} | max {l["silabas"]} syllables | {l["segundos"]:.1f}s | {l["texto"]}'
            + (f'   <-- {l["aviso"]}' if l.get("aviso") else "") for l in lineas)
        previo = (f"Song summary:\n{resumen}\n\n" if resumen else "") + (
            f"Full lyrics (context only, do not translate this block):\n{contexto}\n\n" if contexto else "")
        return interpretar_respuesta(self._chat(_instrucciones(origen, destino),
                                                f"{previo}Items to adapt:\n{entrada}", _ESQUEMA))

    def revisar_lote(self, lineas: list[dict], destino: str, resumen: str = "") -> dict[int, str]:
        entrada = "\n".join(f'{l["n"]} | max {l["silabas"]} syllables | original: {l["original"]} '
                            f'| adaptation: {l["texto"]}' for l in lineas)
        previo = f"Song summary:\n{resumen}\n\n" if resumen else ""
        return interpretar_respuesta(self._chat(_instrucciones_revision(destino),
                                                f"{previo}Lines to proofread:\n{entrada}", _ESQUEMA_REVISION))
    def liberar(self) -> None:
        """Pide a Ollama que descargue el modelo y espera a que la VRAM quede libre."""
        try:
            httpx.post(f"{self.url}/api/generate", json={"model": self.nombre, "keep_alive": 0}, timeout=30)
            for _ in range(40):
                cargados = httpx.get(f"{self.url}/api/ps", timeout=10).json().get("models", [])
                if not any(m.get("name") == self.nombre for m in cargados):
                    return
                time.sleep(0.5)
            log.warning("Ollama no descargó %s a tiempo", self.nombre)
        except httpx.HTTPError as e:
            log.warning("no se pudo descargar %s de Ollama: %s", self.nombre, e)


class TraductorGemini(TraductorOllama):
    """Mismos prompts que Ollama (resumen, adaptación y revisión), servidos por la API de Gemini.

    Prueba los modelos de GEMINI_MODELOS en orden: si uno está saturado (429/5xx) o no responde tras
    GEMINI_REINTENTOS intentos, pasa al siguiente y se queda con él para el resto de la canción.
    """

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    _REINTENTABLES = {429, 500, 502, 503, 504}

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if not cfg.gemini_api_key:
            raise ErrorPipeline("falta GEMINI_API_KEY para traducir con Gemini")
        self.modelos = cfg.catalogo_gemini
        if not self.modelos:
            raise ErrorPipeline("GEMINI_MODELOS está vacío")
        self._indice = 0
        self.nombre, self.nivel, self.nivel_pedido = self.modelos[0], "gemini", "gemini"
        self.motivo_nivel = None
        log.info("LLM: Gemini (%s)", ", ".join(self.modelos))

    def instalados(self) -> list[str]:
        return list(self.modelos)

    def _peticion(self, modelo: str, sistema: str, usuario: str, json_salida: bool,
                  razonar: bool) -> httpx.Response:
        generacion: dict = {"temperature": self.cfg.llm_temperatura,
                            "seed": self.cfg.llm_semilla + getattr(self, "_intento", 0)}
        if json_salida:
            generacion["responseMimeType"] = "application/json"
        if razonar and self.cfg.gemini_razonamiento:
            generacion["thinkingConfig"] = {"thinkingLevel": self.cfg.gemini_razonamiento}
        cuerpo = {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user", "parts": [{"text": usuario}]}],
            "generationConfig": generacion,
        }
        return httpx.post(self.URL.format(modelo=modelo), json=cuerpo, timeout=self.cfg.gemini_timeout_s,
                          headers={"x-goog-api-key": self.cfg.gemini_api_key})

    def _chat(self, sistema: str, usuario: str, esquema: dict | None = None, pensar: bool = False) -> str:
        ultimo_error = "sin respuesta"
        while self._indice < len(self.modelos):
            modelo = self.modelos[self._indice]
            razonar = True
            for intento in range(self.cfg.gemini_reintentos + 1):
                try:
                    r = self._peticion(modelo, sistema, usuario, esquema is not None, razonar)
                    if r.status_code == 400 and razonar and "think" in r.text.lower():
                        razonar = False  # el modelo no admite thinkingLevel: se repite sin él
                        r = self._peticion(modelo, sistema, usuario, esquema is not None, razonar)
                except httpx.TimeoutException:
                    ultimo_error = f"{modelo}: no respondió en {self.cfg.gemini_timeout_s:.0f} s"
                    break  # un modelo que no responde a tiempo no se reintenta: se pasa al siguiente
                except httpx.HTTPError as e:
                    ultimo_error = f"{modelo}: {type(e).__name__}"
                    time.sleep(2 * (intento + 1))
                    continue
                if r.status_code in self._REINTENTABLES:
                    ultimo_error = f"{modelo}: HTTP {r.status_code}"
                    time.sleep(5 * (intento + 1))  # saturación pasajera: se espera antes de bajar de modelo
                    continue
                if not r.is_success:  # 400/403/404: este modelo no sirve, se pasa al siguiente
                    ultimo_error = f"{modelo}: HTTP {r.status_code} {r.text[:200]}"
                    break
                texto = self._texto(r.json())
                if texto:
                    return texto
                ultimo_error = f"{modelo}: respuesta vacía"
            # este modelo no respondió: se pasa al siguiente y se queda en él
            log.warning("Gemini %s no disponible (%s): se prueba el siguiente modelo", modelo, ultimo_error)
            self._indice += 1
            if self._indice < len(self.modelos):
                self.nombre = self.modelos[self._indice]
                self.motivo_nivel = f"{modelo} no disponible ({ultimo_error}): se usó {self.nombre}"
        raise ErrorPipeline(f"ningún modelo de Gemini respondió ({ultimo_error})")

    @staticmethod
    def _texto(datos: dict) -> str:
        candidatos = datos.get("candidates") or []
        if not candidatos:
            return ""
        partes = candidatos[0].get("content", {}).get("parts", [])
        texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
        return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()

    def liberar(self) -> None:
        """La API no ocupa VRAM local: no hay nada que liberar."""


def crear_traductor(cfg: Config) -> Traductor:
    if cfg.llm_proveedor == "ollama":
        return TraductorOllama(cfg)
    if cfg.llm_proveedor == "gemini":
        return TraductorGemini(cfg)
    raise ErrorPipeline(f"LLM_PROVEEDOR={cfg.llm_proveedor} no está implementado")


def acortar_frases(letra: dict, pedidos: list[dict], cfg: Config, timeout_s: float | None = None) -> dict[int, str]:
    """MusicAI: versos que, sintetizados, no caben en su tiempo ni acelerando → versión más corta.

    letra: el letra.json traducido ({idioma_origen, idioma_destino, resumen, frases}).
    pedidos: [{i, texto (traducción actual), original, silabas (máximo nuevo), segundos}].
    Devuelve {i: texto más corto}; solo incluye los que de verdad tienen menos sílabas. Nunca lanza
    error: si el LLM falla o tarda más de `timeout_s`, devuelve {} y el sintetizador sigue con el
    rescate por tempo / recorte en pausa.
    """
    import concurrent.futures

    if not pedidos:
        return {}
    origen, destino = letra.get("idioma_origen") or "en", letra["idioma_destino"]
    contexto = "\n".join(f.get("original", "") for f in letra.get("frases", []))
    lineas = [{"n": k, "texto": p["original"] or p["texto"], "silabas": p["silabas"], "segundos": p["segundos"],
               "aviso": f'your version "{p["texto"]}" has {contar_silabas(p["texto"], destino)} syllables and '
                        f'does not fit in the time when sung: rewrite it shorter, at most {p["silabas"]} '
                        "syllables, keeping the meaning and every word complete"}
              for k, p in enumerate(pedidos, start=1)]

    def pedir() -> dict[int, str]:
        traductor = crear_traductor(cfg)
        try:
            return traductor.traducir_lote(lineas, origen, destino, contexto=contexto,
                                           resumen=letra.get("resumen") or "")
        finally:
            traductor.liberar()

    hilo = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        respuesta = hilo.submit(pedir).result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        log.warning("acortar versos: el LLM no respondió en %.0f s; se sigue sin acortar", timeout_s or 0)
        return {}
    except Exception as e:  # noqa: BLE001 - acortar es una mejora: nunca debe tumbar el trabajo
        log.warning("acortar versos: el LLM falló (%s); se sigue sin acortar", e)
        return {}
    finally:
        hilo.shutdown(wait=False)
    nuevos = {}
    for k, p in enumerate(pedidos, start=1):
        texto = (respuesta.get(k) or "").strip()
        if texto and contar_silabas(texto, destino) < contar_silabas(p["texto"], destino):
            nuevos[p["i"]] = texto
    log.info("acortar versos: %d de %d versos con una versión más corta", len(nuevos), len(pedidos))
    return nuevos


def interpretar_respuesta(contenido: str) -> dict[int, str]:
    """Extrae {n: texto} del JSON del modelo; devuelve {} si no se puede leer."""
    contenido = re.sub(r"<think>.*?</think>", "", contenido, flags=re.DOTALL).strip()
    inicio, fin = contenido.find("{"), contenido.rfind("}")
    if inicio < 0 or fin <= inicio:
        return {}
    try:
        datos = json.loads(contenido[inicio:fin + 1])
    except json.JSONDecodeError:
        return {}
    resultado: dict[int, str] = {}
    for linea in datos.get("lineas", []) if isinstance(datos, dict) else []:
        try:
            texto = " ".join(str(linea["texto"]).split())
            if texto:
                resultado[int(linea["n"])] = texto
        except (KeyError, TypeError, ValueError):
            continue
    return resultado


# ---------- Etapa ----------

def _traducir_lineas(traductor: Traductor, lineas: list[dict], origen: str, destino: str,
                     contexto: str = "", resumen: str = "") -> dict[int, str]:
    """Traduce por lotes; reintenta las líneas que el modelo se salte."""
    hechas: dict[int, str] = {}

    def pedir(grupo: list[dict]) -> None:
        # cada petición se numera 1..k: los modelos tienden a renumerar desde 1 y así siempre coincide
        locales = [{**l, "n": k} for k, l in enumerate(grupo, start=1)]
        respuesta = traductor.traducir_lote(locales, origen, destino, contexto=contexto, resumen=resumen)
        for k, l in enumerate(grupo, start=1):
            if k in respuesta:
                hechas[l["n"]] = respuesta[k]

    for i in range(0, len(lineas), TAMANO_LOTE):
        lote = lineas[i:i + TAMANO_LOTE]
        pendientes = lote
        for intento in range(2):
            traductor.variar(intento)  # con semilla fija, repetir tal cual daría la misma omisión
            pedir(pendientes)
            pendientes = [l for l in lote if l["n"] not in hechas]
            if not pendientes:
                break
            log.warning("el LLM omitió %d líneas (intento %d)", len(pendientes), intento + 1)
        for l in pendientes:  # último recurso: una por una
            pedir([l])
        traductor.variar(0)
    return hechas


def presupuesto_silabas(frases: list[dict], i: int, silabas_por_segundo: float,
                        holgura_max_s: float = 0.4) -> int:
    """Sílabas que caben dichas en el verso i: su duración (más algo del silencio que le sigue)
    por la velocidad a la que habla el sintetizador."""
    f = frases[i]
    hueco = frases[i + 1]["inicio"] - f["fin"] if i + 1 < len(frases) else holgura_max_s
    disponible = f["fin"] - f["inicio"] + min(max(0.0, hueco), holgura_max_s)
    return max(2, round(disponible * silabas_por_segundo))


def _ajustar_al_presupuesto(traductor: Traductor, lineas: list[dict], hechas: dict[int, str], origen: str,
                            destino: str, contexto: str, reintentos: int, resumen: str = "") -> None:
    """Vuelve a pedir las frases que se pasan de sílabas; se queda con la versión más corta."""
    for intento in range(reintentos):
        largas = [{**l, "aviso": f'your version "{hechas[l["n"]]}" has {contar_silabas(hechas[l["n"]], destino)} '
                                 f'syllables, too long: rewrite it shorter, at most {l["silabas"]} syllables'}
                  for l in lineas if l["n"] in hechas and contar_silabas(hechas[l["n"]], destino) > l["silabas"]]
        if not largas:
            return
        log.info("%d frases se pasan de sílabas: reintento %d", len(largas), intento + 1)
        for n, texto in _traducir_lineas(traductor, largas, origen, destino, contexto, resumen).items():
            if contar_silabas(texto, destino) < contar_silabas(hechas[n], destino):
                hechas[n] = texto
    for l in lineas:
        if l["n"] in hechas and contar_silabas(hechas[l["n"]], destino) > l["silabas"]:
            log.warning("frase %d sigue larga: %d sílabas para un máximo de %d", l["n"],
                        contar_silabas(hechas[l["n"]], destino), l["silabas"])


def _clave(texto: str) -> str:
    return re.sub(r"[\W_]+", " ", texto.lower()).strip()


def _unificar_repetidas(lineas: list[dict], hechas: dict[int, str], destino: str) -> None:
    """Una frase que se repite (estribillo) se canta igual todas las veces: gana la versión más
    corta, siempre que quepa en el presupuesto de cada repetición."""
    grupos: dict[str, list[dict]] = {}
    for l in lineas:
        if l["n"] in hechas:
            grupos.setdefault(_clave(l["texto"]), []).append(l)
    for iguales in grupos.values():
        if len(iguales) > 1:
            mejor = min((hechas[l["n"]] for l in iguales), key=lambda t: contar_silabas(t, destino))
            for l in iguales:
                if contar_silabas(mejor, destino) <= max(l["silabas"], contar_silabas(hechas[l["n"]], destino)):
                    hechas[l["n"]] = mejor


def _revisar(traductor: Traductor, lineas: list[dict], hechas: dict[int, str], destino: str,
             resumen: str = "") -> int:
    """Segunda pasada del LLM: corrige gramática, concordancia y naturalidad.

    Una corrección solo se acepta si no alarga el verso más allá de su presupuesto (o de lo que ya
    medía) y no lo deja a medias. Devuelve cuántas frases cambió.
    """
    cambiadas = 0
    pendientes = [l for l in lineas if l["n"] in hechas]
    for i in range(0, len(pendientes), TAMANO_LOTE):
        lote = pendientes[i:i + TAMANO_LOTE]
        locales = [{"n": k, "original": l["texto"], "texto": hechas[l["n"]], "silabas": l["silabas"]}
                   for k, l in enumerate(lote, start=1)]
        respuesta = traductor.revisar_lote(locales, destino, resumen)
        for k, l in enumerate(lote, start=1):
            nueva, actual = respuesta.get(k, "").strip(), hechas[l["n"]]
            if not nueva or nueva == actual:
                continue
            antes, ahora = contar_silabas(actual, destino), contar_silabas(nueva, destino)
            if ahora > max(l["silabas"], antes) or ahora < 0.6 * antes:
                log.info("revisión descartada en la frase %d (%d → %d sílabas, máximo %d)",
                         l["n"], antes, ahora, l["silabas"])
                continue
            hechas[l["n"]] = nueva
            cambiadas += 1
    return cambiadas

def traducir(letra_json: Path, json_salida: Path, idioma_destino: str,
             cfg: Config | None = None, traductor: Traductor | None = None) -> Path:
    """letra original → JSON {idioma_origen, idioma_destino, modelo, nivel_llm_pedido, nivel_llm_usado,
    [motivo_nivel_llm], resumen, frases: [{inicio, fin, original, texto}]}."""
    cfg = cfg or obtener_config()
    letra = json.loads(Path(letra_json).read_text(encoding="utf-8"))
    origen, frases = letra.get("idioma", "auto"), letra["frases"]
    modelo, resumen = "ninguno", ""
    nivel = {"nivel_llm_pedido": cfg.llm_nivel, "nivel_llm_usado": None}  # sin traducción no se usa ninguno

    textos = {i: f["texto"] for i, f in enumerate(frases)}  # por defecto, el original
    grupos = agrupar_en_oraciones(frases, origen)
    if origen != idioma_destino and grupos:
        propio = traductor is None
        traductor = traductor or crear_traductor(cfg)
        modelo = traductor.nombre
        nivel = {"nivel_llm_pedido": traductor.nivel_pedido or cfg.llm_nivel, "nivel_llm_usado": traductor.nivel}
        if traductor.motivo_nivel:
            nivel["motivo_nivel_llm"] = traductor.motivo_nivel
        lineas = []
        for n, grupo in enumerate(grupos, start=1):
            versos = [frases[i] for i in grupo]
            lineas.append({"n": n, "texto": " ".join(v["texto"] for v in versos),
                           "segundos": versos[-1]["fin"] - versos[0]["inicio"],
                           "silabas": sum(presupuesto_silabas(frases, i, cfg.silabas_por_segundo)
                                          for i in grupo)})
        contexto = "\n".join(f["texto"] for f in frases)
        try:
            # 1) el modelo lee toda la letra y resume de qué trata y qué tono tiene
            if cfg.llm_resumen:
                resumen = traductor.resumir(contexto, origen)
                log.info("resumen de la canción: %s", resumen or "(vacío)")
            # 2) traducción por tandas, con el resumen y la letra completa como contexto
            hechas = _traducir_lineas(traductor, lineas, origen, idioma_destino, contexto, resumen)
            _ajustar_al_presupuesto(traductor, lineas, hechas, origen, idioma_destino, contexto,
                                    cfg.reintentos_silabas, resumen)
            _unificar_repetidas(lineas, hechas, idioma_destino)
            # 3) segunda pasada: solo gramática, concordancia y naturalidad
            if cfg.llm_revision:
                cambiadas = _revisar(traductor, lineas, hechas, idioma_destino, resumen)
                _unificar_repetidas(lineas, hechas, idioma_destino)
                log.info("revisión: %d frases corregidas", cambiadas)
        finally:
            if propio:
                traductor.liberar()  # la GPU debe quedar libre antes de la síntesis
        # Gemini puede haber cambiado de modelo a mitad de camino (respaldo): se informa el usado.
        modelo = traductor.nombre
        if traductor.motivo_nivel:
            nivel["motivo_nivel_llm"] = traductor.motivo_nivel
        faltan = [l["n"] for l in lineas if l["n"] not in hechas]
        if len(faltan) > len(lineas) / 2:
            raise ErrorPipeline(f"el LLM {modelo} no devolvió una traducción utilizable")
        for n in faltan:
            log.warning("frase %d sin traducir: se conserva el original", n)
        for n, grupo in enumerate(grupos, start=1):
            if n in hechas:  # la frase traducida se reparte entre sus versos según lo que dura cada uno
                pesos = [frases[i]["fin"] - frases[i]["inicio"] for i in grupo]
                for i, trozo in zip(grupo, repartir_texto(hechas[n], pesos, idioma_destino)):
                    textos[i] = trozo
        log.info("%d versos traducidos como %d frases completas", sum(map(len, grupos)), len(grupos))

    salida = {
        "idioma_origen": origen, "idioma_destino": idioma_destino, "modelo": modelo, **nivel,
        "resumen": resumen,
        "frases": [{"inicio": f["inicio"], "fin": f["fin"], "original": f["texto"], "texto": textos[i],
                    **({"conservar": True} if f.get("conservar") else {})}
                   for i, f in enumerate(frases)],
    }
    json_salida = Path(json_salida)
    json_salida.parent.mkdir(parents=True, exist_ok=True)
    json_salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_salida
