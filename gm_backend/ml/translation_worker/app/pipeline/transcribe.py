"""Etapa 3 — transcribir la voz con faster-whisper: letra con tiempos por frase."""
import json
import logging
import os
from pathlib import Path

from app.config import Config, obtener_config, preparar_entorno_modelos
from app.errores import EntradaInvalida
from app.gpu import liberar_vram
from app.media import ffmpeg
from app.pipeline.letra import alinear_letra, separar_interjecciones, unir_frases_cortas

log = logging.getLogger("worker.transcribir")


def _preparar_dlls_cuda() -> None:
    """En Windows, ctranslate2 necesita encontrar cuDNN/cuBLAS: usamos los que trae torch."""
    if os.name != "nt":
        return
    import torch

    lib = Path(torch.__file__).parent / "lib"
    if lib.is_dir() and str(lib) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{lib}{os.pathsep}{os.environ.get('PATH', '')}"
        os.add_dll_directory(str(lib))


_FIN_DE_FRASE = (".", "?", "!", "。", "？", "！")


def detectar_silencios(audio, sr: int, min_s: float = 0.35) -> list[tuple[float, float]]:
    """Tramos (inicio, fin) en segundos donde la voz está callada: las pausas entre versos."""
    import numpy as np

    tramo = int(0.02 * sr)
    n = len(audio) // tramo
    if n == 0:
        return []
    rms = np.sqrt(np.mean(np.asarray(audio[: n * tramo], dtype=np.float32).reshape(n, tramo) ** 2, axis=1))
    fuerte = float(np.percentile(rms, 95))
    if fuerte < 1e-4:
        return [(0.0, n * tramo / sr)]
    callado = np.append(rms < fuerte * 0.1, False)  # 20 dB por debajo de la voz
    silencios, inicio = [], None
    for i, c in enumerate(callado):
        if c and inicio is None:
            inicio = i
        elif not c and inicio is not None:
            if (i - inicio) * tramo / sr >= min_s:
                silencios.append((inicio * tramo / sr, i * tramo / sr))
            inicio = None
    return silencios


def ajustar_palabras_a_la_voz(palabras: list[dict], silencios: list[tuple[float, float]],
                              min_voz_s: float = 0.08) -> list[dict]:
    """Whisper estira las palabras hasta cubrir las pausas; aquí cada una se recorta a su parte con voz.

    Así las pausas reales reaparecen como huecos entre palabras y sirven para cortar los versos.
    """
    ajustadas = []
    for p in palabras:
        ini, fin = p["inicio"], p["fin"]
        partes, cursor = [], ini
        for a, b in silencios:
            if b <= ini or a >= fin:
                continue
            if a > cursor:
                partes.append((cursor, a))
            cursor = max(cursor, b)
        if cursor < fin:
            partes.append((cursor, fin))
        mejor = max(partes, key=lambda x: x[1] - x[0], default=None)
        pausa_tras = next((b for a, b in silencios if mejor and abs(a - mejor[1]) < 0.02), None)
        if mejor and mejor[0] == p["inicio"] and mejor[1] - mejor[0] < 0.25 and pausa_tras:
            # solo un resto de voz al principio y luego la pausa: ese resto es la cola de la palabra
            # anterior, y esta palabra en realidad suena al volver la voz
            ini, fin = pausa_tras, max(fin, pausa_tras)
        elif mejor and mejor[1] - mejor[0] >= min_voz_s:
            ini, fin = mejor
        elif fin - ini > 0.3:
            ini = fin - 0.3  # todo cae en silencio: la pausa suele ir pegada al inicio de la palabra
        ajustadas.append({**p, "inicio": ini, "fin": fin})
    return ajustadas


def _partir_largo(grupo: list[dict], max_s: float) -> list[list[dict]]:
    """Parte un verso demasiado largo por su mayor hueco interno (o por la mitad si no hay huecos)."""
    if len(grupo) < 2 or grupo[-1]["fin"] - grupo[0]["inicio"] <= max_s:
        return [grupo]
    medio = (len(grupo) - 1) / 2
    k = max(range(len(grupo) - 1),
            key=lambda i: (round(grupo[i + 1]["inicio"] - grupo[i]["fin"], 2), -abs(i - medio)))
    return _partir_largo(grupo[: k + 1], max_s) + _partir_largo(grupo[k + 1:], max_s)


def _frase(grupo: list[dict]) -> dict:
    return {"inicio": grupo[0]["inicio"], "fin": grupo[-1]["fin"], "texto": "".join(p["texto"] for p in grupo)}


def dividir_en_frases(palabras: list[dict], pausa_s: float = 0.45, max_s: float = 7.0) -> list[dict]:
    """Agrupa palabras [{inicio, fin, texto, segmento}] en versos (ver agrupar_en_versos)."""
    return [_frase(g) for g in agrupar_en_versos(palabras, pausa_s, max_s)]


def agrupar_en_versos(palabras: list[dict], pausa_s: float = 0.45, max_s: float = 7.0) -> list[list[dict]]:
    """Agrupa palabras [{inicio, fin, texto, segmento}] en versos (listas de palabras).

    Corta cuando cambia el segmento de Whisper, hay una pausa o termina una oración.
    Un verso que aun así quede demasiado largo se parte por su mayor hueco.
    """
    grupos: list[list[dict]] = []
    for p in palabras:
        if grupos:
            actual = grupos[-1]
            previa = actual[-1]
            duracion = previa["fin"] - actual[0]["inicio"]
            if not (p["segmento"] != previa["segmento"]
                    or p["inicio"] - previa["fin"] >= pausa_s
                    or (previa["texto"].strip().endswith(_FIN_DE_FRASE) and duracion >= 1.0)):
                actual.append(p)
                continue
        grupos.append([p])
    return [g for grupo in grupos for g in _partir_largo(grupo, max_s)]


# ---------- MusicAI: tramos que Whisper se salta ----------
# Whisper decodifica por ventanas de 30 s. En una ventana difícil (p. ej. el rap de «Levitating»
# separado con RoFormer) puede devolver solo una alucinación y saltar al final de la ventana: se pierden
# ~30 s de letra aunque la voz suena a pleno volumen. Transcribiendo de nuevo SOLO ese tramo, Whisper
# lo saca entero. Aquí se detectan esos tramos (voz sin palabras) y se vuelven a transcribir.

# Frases que Whisper inventa sobre música o silencio (subtítulos de YouTube): se descartan si van solas.
_ALUCINACIONES = {
    "thank you", "thanks for watching", "thank you for watching", "well be right back", "subscribe",
    "please subscribe", "subtitles by the amaraorg community", "music", "applause", "gracias",
    "gracias por ver el video", "suscribete", "merci", "sous-titrage st 501",
}


def _clave_texto(texto: str) -> str:
    import re
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"['’`]", "", texto)  # we'll → well
    return " ".join(re.sub(r"[^\w\s]", " ", texto).split())


def es_alucinacion(texto: str) -> bool:
    """Texto típico que Whisper inventa (o solo símbolos como «🎵»)."""
    clave = _clave_texto(texto)
    return not clave or clave in _ALUCINACIONES


def mascara_voz(audio, sr: int, tramo_s: float = 0.02):
    """Por cada cuadro de 20 ms: True si la voz suena (menos de 20 dB por debajo de su parte fuerte)."""
    import numpy as np

    tramo = int(tramo_s * sr)
    n = len(audio) // tramo
    if n == 0:
        return np.zeros(0, dtype=bool)
    rms = np.sqrt(np.mean(np.asarray(audio[: n * tramo], dtype=np.float32).reshape(n, tramo) ** 2, axis=1))
    fuerte = float(np.percentile(rms, 95))
    return rms > fuerte * 0.1 if fuerte >= 1e-4 else np.zeros(n, dtype=bool)


def tramos_sin_letra(palabras: list[dict], voz, total_s: float, tramo_s: float = 0.02,
                     min_voz_s: float = 3.0, max_aisladas: int = 8, aislada_hueco_s: float = 3.0) -> list[tuple[float, float]]:
    """Tramos (inicio, fin) con al menos `min_voz_s` segundos de voz y sin palabras transcritas.

    Unas pocas palabras sueltas (≤ max_aisladas) rodeadas de huecos largos no cortan el tramo: suelen ser
    la alucinación que Whisper puso en lugar de la letra (p. ej. «We'll be right back» a mitad del rap).
    """
    import numpy as np

    def voz_entre(a: float, b: float) -> float:
        i, j = max(0, int(a / tramo_s)), min(len(voz), int(b / tramo_s))
        return float(np.count_nonzero(voz[i:j])) * tramo_s if j > i else 0.0

    orden = sorted(palabras, key=lambda p: p["inicio"])
    # huecos entre palabras consecutivas (y al principio y al final)
    bordes = [0.0] + [x for p in orden for x in (p["inicio"], p["fin"])] + [total_s]
    huecos = [(bordes[k], bordes[k + 1]) for k in range(0, len(bordes) - 1, 2) if bordes[k + 1] > bordes[k]]
    candidatos = [h for h in huecos if voz_entre(*h) >= min_voz_s]
    if not candidatos:
        return []
    # unir candidatos separados solo por unas pocas palabras sueltas
    unidos = [list(candidatos[0])]
    for a, b in candidatos[1:]:
        entre = [p for p in orden if p["inicio"] >= unidos[-1][1] - 1e-6 and p["fin"] <= a + 1e-6]
        duracion = (entre[-1]["fin"] - entre[0]["inicio"]) if entre else 0.0
        if len(entre) <= max_aisladas and duracion <= aislada_hueco_s:
            unidos[-1][1] = b
        else:
            unidos.append([a, b])
    return [(round(a, 2), round(b, 2)) for a, b in unidos]


def recuperar_tramos(modelo, audio, sr: int, palabras: list[dict], idioma: str | None, opciones: dict,
                     margen_s: float = 1.0) -> tuple[list[dict], list[dict]]:
    """Vuelve a transcribir los tramos con voz y sin letra. Devuelve (palabras, informe).

    Las palabras nuevas sustituyen a las que había dentro del tramo solo si son más (si la segunda pasada
    no encuentra más letra, se deja todo como estaba).
    """
    import numpy as np

    total_s = len(audio) / sr
    voz = mascara_voz(audio, sr)
    tramos = tramos_sin_letra(palabras, voz, total_s)
    informe = []
    siguiente_segmento = max((p["segmento"] for p in palabras), default=-1) + 1000
    for a, b in tramos:
        desde, hasta = max(0.0, a - margen_s), min(total_s, b + margen_s)
        trozo = audio[int(desde * sr): int(hasta * sr)]
        segmentos, _ = modelo.transcribe(trozo, language=idioma, **opciones)
        nuevas = []
        for k, s in enumerate(segmentos):
            if es_alucinacion(s.text):
                continue
            for p in s.words or []:
                inicio, fin = desde + p.start, desde + p.end
                if a - 0.05 <= (inicio + fin) / 2 <= b + 0.05:  # solo lo que cae dentro del tramo
                    nuevas.append({"inicio": inicio, "fin": fin, "texto": p.word,
                                   "segmento": siguiente_segmento + k})
        siguiente_segmento += 1000
        viejas = [p for p in palabras if a - 0.05 <= (p["inicio"] + p["fin"]) / 2 <= b + 0.05]
        segundos_voz = float(np.count_nonzero(voz[int(a / 0.02): int(b / 0.02)])) * 0.02
        # una letra real trae bastantes palabras por segundo de voz; pocas palabras sobre mucha «voz»
        # suelen ser restos del instrumental que Whisper interpreta como texto inventado
        aceptado = len(nuevas) > len(viejas) and len(nuevas) >= 0.3 * segundos_voz
        informe.append({"inicio": a, "fin": b, "segundos_voz": round(segundos_voz, 1),
                        "palabras_antes": len(viejas), "palabras_despues": len(nuevas),
                        "aceptado": aceptado,
                        "texto": "".join(p["texto"] for p in nuevas).strip()[:300]})
        log.info("tramo %.1f-%.1fs con voz y sin letra: segunda pasada %d palabras (antes %d) → %s",
                 a, b, len(nuevas), len(viejas), "se usa" if aceptado else "se descarta")
        if aceptado:
            ids = {id(p) for p in viejas}
            palabras = sorted([p for p in palabras if id(p) not in ids] + nuevas, key=lambda p: p["inicio"])
    return palabras, informe


def normalizar_frases(segmentos: list[dict]) -> list[dict]:
    """Limpia la salida de Whisper: quita vacíos, repeticiones seguidas y tiempos imposibles."""
    frases: list[dict] = []
    for s in segmentos:
        texto = " ".join(str(s["texto"]).split())
        inicio, fin = float(s["inicio"]), float(s["fin"])
        if not texto or fin - inicio < 0.2:
            continue
        if frases and frases[-1]["texto"].lower() == texto.lower() and inicio - frases[-1]["fin"] < 0.3:
            continue  # alucinación típica: la misma frase pegada a la anterior
        if frases and inicio < frases[-1]["fin"]:
            inicio = frases[-1]["fin"]
            if fin - inicio < 0.2:
                continue
        frases.append({"inicio": round(inicio, 2), "fin": round(fin, 2), "texto": texto,
                       **({"conservar": True} if s.get("conservar") else {})})
    return frases


def transcribir(voz_wav: Path, json_salida: Path, cfg: Config | None = None,
                idioma: str = "auto", letra_original: str | None = None,
                letra_obligatoria: bool = True) -> Path:
    """voz.wav → JSON {idioma, letra_alineada, frases: [{inicio, fin, texto}]}.

    Si se da `letra_original` (un verso por línea), Whisper solo aporta los tiempos: el texto y el
    corte de versos salen de esa letra. Si la letra no coincide con lo que se canta: con
    `letra_obligatoria` es un error (la dio el usuario); sin ella (vino de LRCLIB) se ignora.
    """
    cfg = cfg or obtener_config()
    preparar_entorno_modelos(cfg)
    _preparar_dlls_cuda()
    import soundfile as sf
    import torch
    from faster_whisper import WhisperModel

    # Whisper trabaja a 16 kHz mono. Lo decodificamos con FFmpeg y le pasamos el audio en memoria:
    # así no dependemos del decodificador PyAV de faster-whisper (incompatible con av >= 16).
    json_salida = Path(json_salida)
    json_salida.parent.mkdir(parents=True, exist_ok=True)
    wav_16k = json_salida.with_name(json_salida.stem + "_16k.wav")
    ffmpeg(["-i", voz_wav, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav_16k], cfg)
    audio, _ = sf.read(str(wav_16k), dtype="float32")
    wav_16k.unlink(missing_ok=True)

    cuda = cfg.dispositivo == "cuda" and torch.cuda.is_available()
    modelo = WhisperModel(cfg.whisper_modelo, device="cuda" if cuda else "cpu",
                          compute_type=cfg.whisper_compute if cuda else "int8")
    opciones = dict(
        beam_size=5,
        # Sin VAD por defecto: al recortar los silencios, Whisper pegaba versos entre sí y
        # perdía la puntuación (medido en la fase 1). La voz ya viene aislada por Demucs.
        vad_filter=cfg.whisper_vad,
        condition_on_previous_text=False,
        word_timestamps=True,  # tiempos por palabra para cortar los versos en las pausas reales
        hallucination_silence_threshold=2.0,  # descarta texto inventado sobre silencios largos
    )
    diagnostico: dict = {"segmentos": [], "descartados": [], "tramos_recuperados": []}
    try:
        segmentos, info = modelo.transcribe(
            audio, language=None if idioma in ("auto", "", None) else idioma, **opciones)
        palabras = []
        for i, s in enumerate(segmentos):
            datos = {"inicio": round(s.start, 2), "fin": round(s.end, 2), "texto": s.text.strip(),
                     "no_speech_prob": round(s.no_speech_prob, 3), "avg_logprob": round(s.avg_logprob, 3),
                     "compression_ratio": round(s.compression_ratio, 2), "temperatura": s.temperature}
            # MusicAI: «We'll be right back», «Thank you», «🎵»... con poca confianza: inventados por Whisper
            if es_alucinacion(s.text) and (s.no_speech_prob > 0.5 or s.avg_logprob < -0.5):
                diagnostico["descartados"].append(datos)
                log.info("descartada alucinación de Whisper %.1f-%.1fs: «%s»", s.start, s.end, s.text.strip())
                continue
            diagnostico["segmentos"].append(datos)
            palabras += [{"inicio": p.start, "fin": p.end, "texto": p.word, "segmento": i} for p in (s.words or [])]
        detectado = info.language
        if cfg.whisper_recuperar_tramos and palabras:
            palabras, diagnostico["tramos_recuperados"] = recuperar_tramos(
                modelo, audio, 16000, palabras, detectado, opciones)
        palabras = ajustar_palabras_a_la_voz(palabras, detectar_silencios(audio, 16000))
    finally:
        del modelo
        liberar_vram()
    # diagnóstico de Whisper (se conserva en el modo depuración): qué oyó, con qué confianza y qué se recuperó
    json_salida.with_name("whisper_diagnostico.json").write_text(
        json.dumps({"idioma": detectado, **diagnostico}, ensure_ascii=False, indent=2), encoding="utf-8")

    versos = None
    if letra_original and letra_original.strip() and palabras:
        try:
            versos = alinear_letra(palabras, letra_original, agrupar=agrupar_en_versos)
        except EntradaInvalida as e:
            if letra_obligatoria:
                raise
            log.warning("%s: se usa lo que oyó Whisper", e)
    alineada = versos is not None
    if versos is None:
        versos = agrupar_en_versos(palabras)
    # las interjecciones (oh, hey, la la...) se marcan para conservarlas del audio original
    tramos = [t for v in versos for t in (separar_interjecciones(v) if cfg.conservar_interjecciones else [(v, False)])]
    frases = normalizar_frases([{**_frase(g), **({"conservar": True} if c else {})} for g, c in tramos])
    frases = unir_frases_cortas(frases, cfg.frase_min_s, cfg.union_hueco_max_s)
    log.info("idioma detectado=%s frases=%d (interjecciones conservadas: %d)", detectado, len(frases),
             sum(1 for f in frases if f.get("conservar")))
    json_salida.write_text(json.dumps({"idioma": detectado, "letra_alineada": alineada, "frases": frases},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    return json_salida
