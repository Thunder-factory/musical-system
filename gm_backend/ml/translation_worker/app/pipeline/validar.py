"""MusicAI — validación final: que el video traducido no tenga secciones de la canción desaparecidas.

En la prueba 5d0c3f64 el video terminó «bien» pero sin el primer coro ni el rap (30-96 s): la letra de
LRCLIB no los traía y el verso anterior se estiró 68 s sobre ellos. Nadie lo notó hasta escucharlo.
Esta etapa compara el resultado con la canción original y deja por escrito lo que falta:

- secciones_sin_voz: tramos donde el cantante original canta y la voz nueva calla durante ≥ `min_s`.
- caidas_de_volumen: tramos donde la mezcla final queda muy por debajo de la canción original
  (p. ej. un pasaje casi a cappella sin la voz, o un instrumental que se perdió).
- versos_largos: versos de la letra que duran más de lo que puede durar un verso cantado.

Solo usa numpy/soundfile (CPU, segundos). No modifica ningún archivo de audio.
"""
import json
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger("worker.validar")

_CUADRO_S = 0.02


def _mono(ruta: Path, sr_objetivo: int = 16000) -> np.ndarray:
    import soundfile as sf

    x, sr = sf.read(str(ruta), dtype="float32", always_2d=True)
    x = x.mean(1)
    if sr != sr_objetivo:  # remuestreo simple por interpolación: basta para medir energía
        n = int(len(x) * sr_objetivo / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    return x


def _rms_cuadros(x: np.ndarray, sr: int) -> np.ndarray:
    n = int(_CUADRO_S * sr)
    k = len(x) // n
    if k == 0:
        return np.zeros(0)
    return np.sqrt((x[: k * n].reshape(k, n) ** 2).mean(1) + 1e-12)


def _por_ventana(valores: np.ndarray, ventana_s: float) -> np.ndarray:
    """Media móvil centrada de `ventana_s` sobre una serie por cuadros."""
    w = max(1, int(ventana_s / _CUADRO_S))
    return np.convolve(valores.astype(float), np.ones(w) / w, mode="same")


def _tramos(marca: np.ndarray, min_s: float) -> list[tuple[float, float]]:
    out, i, n = [], 0, len(marca)
    while i < n:
        if marca[i]:
            j = i
            while j < n and marca[j]:
                j += 1
            if (j - i) * _CUADRO_S >= min_s:
                out.append((round(i * _CUADRO_S, 2), round(j * _CUADRO_S, 2)))
            i = j
        else:
            i += 1
    return out


def secciones_sin_voz(voz_original: np.ndarray, voz_nueva: np.ndarray, sr: int, min_s: float = 3.0,
                      ventana_s: float = 1.0) -> list[dict]:
    """Tramos ≥ `min_s` donde la original tiene voz (≥ 50 % de cada ventana) y la nueva casi nada (< 10 %)."""
    ro, rn = _rms_cuadros(voz_original, sr), _rms_cuadros(voz_nueva, sr)
    n = min(len(ro), len(rn))
    if n == 0:
        return []
    ro, rn = ro[:n], rn[:n]
    vo = ro > np.percentile(ro, 95) * 0.1
    ref_n = np.percentile(rn, 95) if rn.max() > 1e-4 else 1.0
    vn = rn > ref_n * 0.1
    fo, fn = _por_ventana(vo, ventana_s), _por_ventana(vn, ventana_s)
    falta = (fo >= 0.5) & (fn < 0.1)
    return [{"desde": a, "hasta": b, "segundos": round(b - a, 1)} for a, b in _tramos(falta, min_s)]


def caidas_de_volumen(original: np.ndarray, mezcla: np.ndarray, sr: int, min_s: float = 2.0,
                      umbral_db: float = 12.0, ventana_s: float = 1.0) -> list[dict]:
    """Tramos ≥ `min_s` donde la mezcla queda ≥ `umbral_db` por debajo de la original.

    Antes se compensa la diferencia de volumen general (la mezcla se normaliza a otro LUFS).
    Solo cuenta donde la original suena (no en silencios de la canción).
    """
    ro, rm = _rms_cuadros(original, sr), _rms_cuadros(mezcla, sr)
    n = min(len(ro), len(rm))
    if n == 0:
        return []
    po = _por_ventana(ro[:n] ** 2, ventana_s)
    pm = _por_ventana(rm[:n] ** 2, ventana_s)
    do, dm = 10 * np.log10(po + 1e-12), 10 * np.log10(pm + 1e-12)
    suena = do > np.percentile(do, 95) - 30
    if not suena.any():
        return []
    diferencia = do - dm
    diferencia -= np.median(diferencia[suena])
    cae = suena & (diferencia >= umbral_db)
    salida = []
    for a, b in _tramos(cae, min_s):
        i, j = int(a / _CUADRO_S), int(b / _CUADRO_S)
        salida.append({"desde": a, "hasta": b, "segundos": round(b - a, 1),
                       "caida_db": round(float(np.median(diferencia[i:j])), 1)})
    return salida


def versos_largos(frases: list[dict], max_s: float = 15.0) -> list[dict]:
    return [{"inicio": f["inicio"], "fin": f["fin"], "segundos": round(f["fin"] - f["inicio"], 1),
             "texto": f.get("texto", "")[:80]}
            for f in frases if f["fin"] - f["inicio"] > max_s and not f.get("conservar")]


def sin_traducir(frases: list[dict]) -> list[dict]:
    """Versos que quedaron con el texto original (el LLM no los tradujo)."""
    return [{"inicio": f["inicio"], "texto": f.get("texto", "")[:80]} for f in frases
            if not f.get("conservar") and f.get("original") and f.get("texto") == f.get("original")
            and len(f.get("texto", "").split()) >= 3]


def rellenar_sin_letra(voz_nueva: Path, voz_original: Path, frases: list[dict], wav_salida: Path,
                      min_s: float = 2.0, margen_s: float = 0.3, fundido_s: float = 0.05) -> tuple[Path, list[dict]]:
    """Pone la voz original donde el cantante canta y no hay ningún verso (vocalizaciones, ad-libs).

    Whisper no saca palabras de un «ooh» de 20 s: sin letra no hay nada que traducir y esa parte
    quedaba muda. Igual que las interjecciones, se conserva la voz original. Solo fuera de todo verso
    (± `margen_s`), en tramos con voz de al menos `min_s`, con fundidos de `fundido_s`.
    Devuelve (wav, tramos rellenados).
    """
    import soundfile as sf

    nueva, sr = sf.read(str(voz_nueva), dtype="float32", always_2d=True)
    orig, sr_o = sf.read(str(voz_original), dtype="float32", always_2d=True)
    if sr_o != sr:  # mismo pipeline: deberían coincidir; si no, no se toca nada
        log.warning("relleno sin letra: frecuencias distintas (%d / %d), se omite", sr, sr_o)
        return Path(voz_nueva), []
    orig = orig.mean(1, keepdims=True) if nueva.shape[1] == 1 else np.repeat(orig.mean(1, keepdims=True), nueva.shape[1], 1)
    n = min(len(nueva), len(orig))
    rms = _rms_cuadros(orig[:n, 0], sr)
    if len(rms) == 0:
        return Path(voz_nueva), []
    voz = _por_ventana(rms > np.percentile(rms, 95) * 0.1, 0.5) >= 0.5
    libre = np.ones(len(voz), bool)
    for f in frases:
        a = max(0, int((f["inicio"] - margen_s) / _CUADRO_S))
        libre[a: int((f["fin"] + margen_s) / _CUADRO_S)] = False
    tramos = _tramos(voz & libre, min_s)
    if not tramos:
        return Path(voz_nueva), []
    salida = nueva.copy()
    fundido = int(fundido_s * sr)
    for a, b in tramos:
        i, j = int(a * sr), min(n, int(b * sr))
        if j - i <= 2 * fundido:
            continue
        env = np.ones(j - i, np.float32)
        env[:fundido] = np.linspace(0, 1, fundido)
        env[-fundido:] = np.linspace(1, 0, fundido)
        salida[i:j] = salida[i:j] * (1 - env[:, None]) + orig[i:j] * env[:, None]
        log.info("relleno sin letra: %.1f-%.1fs se canta sin palabras reconocibles → voz original", a, b)
    sf.write(str(wav_salida), salida, sr, subtype="PCM_16")
    return Path(wav_salida), [{"desde": a, "hasta": b, "segundos": round(b - a, 1)} for a, b in tramos]


def validar(voz_original: Path, voz_nueva: Path, audio_original: Path, mezcla: Path, frases: list[dict],
            json_salida: Path | None = None, min_s: float = 3.0, rellenadas: list[dict] | None = None) -> dict:
    """Compara el resultado con la canción original. Devuelve {completo, secciones_sin_voz, ...}."""
    sr = 16000
    perdidas = secciones_sin_voz(_mono(voz_original, sr), _mono(voz_nueva, sr), sr, min_s)
    caidas = caidas_de_volumen(_mono(audio_original, sr), _mono(mezcla, sr), sr)
    largos = versos_largos(frases)
    originales = sin_traducir(frases)
    informe = {
        "completo": not perdidas and not caidas and not largos,
        "segundos_sin_voz": round(sum(p["segundos"] for p in perdidas), 1),
        "secciones_sin_voz": perdidas,
        "caidas_de_volumen": caidas,
        "versos_largos": largos,
        "versos_sin_traducir": originales,
        "con_voz_original_sin_letra": rellenadas or [],
    }
    for p in perdidas:
        log.warning("validación: %.1f-%.1fs el cantante original canta y la voz traducida no (%.1f s)",
                    p["desde"], p["hasta"], p["segundos"])
    for c in caidas:
        log.warning("validación: %.1f-%.1fs la mezcla queda %.0f dB por debajo de la canción original",
                    c["desde"], c["hasta"], c["caida_db"])
    for v in largos:
        log.warning("validación: verso de %.0f s (%.1f-%.1fs) «%s»: probablemente tapa una parte de la canción",
                    v["segundos"], v["inicio"], v["fin"], v["texto"])
    for v in originales:
        log.warning("validación: verso %.1fs sin traducir: «%s»", v["inicio"], v["texto"])
    log.info("validación: %s (%.1f s sin voz, %d caídas de volumen, %d versos largos, %d sin traducir)",
             "completo" if informe["completo"] else "INCOMPLETO", informe["segundos_sin_voz"], len(caidas),
             len(largos), len(originales))
    if json_salida:
        Path(json_salida).write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return informe
