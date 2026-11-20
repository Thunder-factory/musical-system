"""Etapa 5 — sintetizar la voz nueva.

Interfaz `Sintetizador` con dos implementaciones:
  - XttsSintetizador (por defecto): XTTS-v2 clonando el timbre del cantante. Es voz HABLADA
    ajustada al tiempo de cada frase, no cantada.
  - RvcSintetizador (pendiente): convertirá una guía ya cantada al timbre original.
El cambio de timbre con un modelo RVC entrenado (fase 7.3) no es un sintetizador: se aplica después,
a la pista ya armada (app/pipeline/convertir_voz.py, RVC_ACTIVO=true).
La parte común (ajustar la duración y colocar cada frase en su tiempo) vive en la clase base,
así un sintetizador de canto solo tiene que implementar `generar_frases`.
"""
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import Config, obtener_config, preparar_entorno_modelos
from app.errores import ErrorPipeline
from app.gpu import liberar_vram
from app.media import ffmpeg, tiene_filtro
from app.pipeline.letra import escribir_interjeccion

log = logging.getLogger("worker.sintetizar")

FRECUENCIA = 44100
MODOS_INTERJECCIONES = ("original", "sintetizada", "auto")
IDIOMAS_XTTS = {"en": "en", "es": "es", "fr": "fr", "zh": "zh-cn", "de": "de", "it": "it", "pt": "pt",
                "pl": "pl", "tr": "tr", "ru": "ru", "nl": "nl", "cs": "cs", "ar": "ar", "hu": "hu",
                "ko": "ko", "ja": "ja", "hi": "hi"}


# ---------- Utilidades de audio (puras, se prueban sin GPU) ----------

def recortar_silencio(audio: np.ndarray, sr: int, umbral: float = 0.02, margen_s: float = 0.03) -> np.ndarray:
    """Quita el silencio del principio y del final."""
    if audio.size == 0:
        return audio
    fuertes = np.flatnonzero(np.abs(audio) > umbral * max(float(np.abs(audio).max()), 1e-9))
    if fuertes.size == 0:
        return audio[:0]
    margen = int(margen_s * sr)
    return audio[max(0, fuertes[0] - margen): fuertes[-1] + margen + 1]


def duracion_maxima_esperada(texto: str, idioma: str, silabas_por_segundo: float = 4.0) -> float:
    """Segundos que, como mucho, debería durar el texto dicho con calma; más que eso es un fallo del TTS."""
    from app.pipeline.translate import contar_silabas

    return 1.6 * (contar_silabas(texto, idioma) / silabas_por_segundo + 0.5)


def calcular_tempo(duracion_s: float, ventana_s: float, tempo_min: float, tempo_max: float) -> float:
    """Factor de velocidad para que el audio ocupe la ventana, limitado para que siga sonando natural."""
    if duracion_s <= 0 or ventana_s <= 0:
        return 1.0
    return float(min(tempo_max, max(tempo_min, duracion_s / ventana_s)))


def espacio_disponible(frases: list[dict], i: int, total_s: float, margen_s: float = 0.05) -> float:
    """Segundos que puede ocupar el verso i: su tiempo o, si es más, hasta poco antes del verso siguiente."""
    f = frases[i]
    limite = frases[i + 1]["inicio"] if i + 1 < len(frases) else total_s
    return max(f["fin"] - f["inicio"], limite - f["inicio"] - margen_s)


def punto_de_corte(audio: np.ndarray, maximo: int, sr: int = FRECUENCIA, buscar_s: float = 1.5,
                   min_pausa_s: float = 0.04) -> int | None:
    """Última pausa entre palabras antes de `maximo` (en muestras), para cortar sin partir una palabra.

    Una pausa es un tramo de al menos `min_pausa_s` con la energía 20 dB por debajo de la voz. Solo se
    busca en el último `buscar_s` y nunca antes de la mitad del audio (no se tira medio verso).
    Devuelve la muestra donde empieza la pausa (+10 ms) o None si no hay ninguna.
    """
    audio = np.asarray(audio, dtype=np.float32)
    paso = int(0.01 * sr)
    n = min(len(audio), maximo) // paso
    if n < 4:
        return None
    rms = np.sqrt(np.mean(audio[: n * paso].reshape(n, paso) ** 2, axis=1))
    fuerte = float(np.percentile(rms, 95))
    if fuerte <= 1e-6:
        return None
    callado = rms < 0.1 * fuerte
    minimo = max(1, round(min_pausa_s / 0.01))
    desde = max(n // 2, n - int(buscar_s / 0.01))
    k = n - 1
    while k >= desde:  # de atrás hacia delante: la pausa más tardía que quepa
        if callado[k]:
            fin_racha = k
            while k >= 0 and callado[k]:
                k -= 1
            inicio_racha = k + 1
            if fin_racha - inicio_racha + 1 >= minimo and inicio_racha >= desde:
                return (inicio_racha + 1) * paso
        k -= 1
    return None


def ajustar_duracion(wav_entrada: Path, wav_salida: Path, tempo: float, cfg: Config) -> Path:
    """Time-stretch sin cambiar el tono (rubberband si FFmpeg lo trae, si no atempo) y paso a 44.1 kHz mono."""
    filtros = []
    if abs(tempo - 1.0) > 0.03:
        filtros.append(f"rubberband=tempo={tempo:.4f}" if tiene_filtro("rubberband", cfg)
                       else f"atempo={tempo:.4f}")
    filtros.append(f"aresample={FRECUENCIA}")
    ffmpeg(["-i", wav_entrada, "-af", ",".join(filtros), "-ac", "1", "-c:a", "pcm_s16le", wav_salida], cfg)
    return Path(wav_salida)


def preparar_referencia(voz_original: Path, frases: list[dict], wav_salida: Path,
                        max_s: float = 15.0) -> Path:
    """Fragmento limpio del cantante para clonar el timbre: sus frases más largas, hasta max_s."""
    audio, sr = sf.read(str(voz_original), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    trozos, total = [], 0.0
    for f in sorted(frases, key=lambda f: f["fin"] - f["inicio"], reverse=True):
        trozo = mono[int(f["inicio"] * sr): int(f["fin"] * sr)]
        if trozo.size < sr // 2:
            continue
        trozos.append(trozo[: int((max_s - total) * sr)])
        total += trozos[-1].size / sr
        if total >= max_s:
            break
    referencia = np.concatenate(trozos) if trozos else mono[: int(max_s * sr)]
    pico = float(np.abs(referencia).max()) if referencia.size else 0.0
    if pico > 0:
        referencia = referencia / pico * 0.9
    sf.write(str(wav_salida), referencia, sr, subtype="PCM_16")
    return Path(wav_salida)


def leer_mono(wav: Path) -> np.ndarray:
    """WAV → mono float32 a FRECUENCIA."""
    audio, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if sr != FRECUENCIA:  # Demucs entrega 44.1 kHz; por si acaso
        destino = np.arange(round(len(mono) * FRECUENCIA / sr)) * (sr / FRECUENCIA)
        mono = np.interp(destino, np.arange(len(mono)), mono).astype(np.float32)
    return mono


def tramo_interjeccion(frases: list[dict], i: int, total_s: float, antes_s: float = 0.08,
                       despues_s: float = 0.25) -> tuple[float, float]:
    """Tramo (inicio, fin) que puede ocupar la interjección i: su tiempo más un pequeño margen
    (las notas sostenidas duran más que la palabra), sin invadir los versos vecinos."""
    f = frases[i]
    suelo = frases[i - 1]["fin"] if i > 0 else 0.0
    techo = frases[i + 1]["inicio"] if i + 1 < len(frases) else total_s
    a = max(suelo, f["inicio"] - antes_s, 0.0)
    b = min(total_s, max(f["fin"], min(techo, f["fin"] + despues_s)))
    return a, b


def fundir_bordes(audio: np.ndarray, entrada_s: float = 0.03, salida_s: float = 0.05) -> np.ndarray:
    """Fundido corto de entrada y de salida para que no se oiga el corte."""
    audio = np.array(audio, dtype=np.float32)
    n_in = min(len(audio) // 2, int(entrada_s * FRECUENCIA))
    n_out = min(len(audio) // 2, int(salida_s * FRECUENCIA))
    if n_in:
        audio[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype=np.float32)
    if n_out:
        audio[-n_out:] *= np.linspace(1.0, 0.0, n_out, dtype=np.float32)
    return audio


def nivel_voz(audio: np.ndarray) -> float:
    """Volumen (RMS) de la parte con voz, sin contar los silencios."""
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        return 0.0
    activos = audio[np.abs(audio) > 0.1 * float(np.abs(audio).max())]
    return float(np.sqrt(np.mean(activos ** 2))) if activos.size else 0.0


def igualar_volumen(audio: np.ndarray, objetivo: float, ganancia_max: float = 4.0) -> np.ndarray:
    """Lleva el audio al volumen objetivo (con tope de ganancia y sin saturar)."""
    actual = nivel_voz(audio)
    if objetivo <= 0 or actual <= 0:
        return audio
    ganancia = min(ganancia_max, max(1.0 / ganancia_max, objetivo / actual))
    pico = float(np.abs(audio).max()) * ganancia
    if pico > 0.95:
        ganancia *= 0.95 / pico
    return (audio * ganancia).astype(np.float32)


def contar_golpes_de_voz(audio: np.ndarray, sr: int, min_s: float = 0.06) -> int:
    """Número de emisiones de voz separadas por una caída clara de energía (≈ sílabas marcadas).

    Una interjección bien dicha es un sonido sostenido por palabra; si salen más golpes que
    palabras, el TTS la leyó como texto (deletreó o dijo otra cosa).
    """
    tramo = max(1, int(0.02 * sr))
    n = len(audio) // tramo
    if n == 0:
        return 0
    rms = np.sqrt(np.mean(np.asarray(audio[: n * tramo], dtype=np.float32).reshape(n, tramo) ** 2, axis=1))
    if n >= 3:
        rms = np.convolve(rms, np.ones(3) / 3, mode="same")
    if float(rms.max()) < 1e-4:
        return 0
    alto = rms > 0.35 * float(rms.max())
    minimo = max(1, round(min_s / 0.02))
    # tramos seguidos por encima / por debajo del umbral
    rachas: list[list] = []
    for v in alto:
        if rachas and rachas[-1][0] == bool(v):
            rachas[-1][1] += 1
        else:
            rachas.append([bool(v), 1])
    # una caída demasiado breve no separa dos golpes: se rellena
    for k in range(1, len(rachas) - 1):
        if not rachas[k][0] and rachas[k][1] < minimo:
            rachas[k][0] = True
    golpes, previo, largo = 0, False, 0
    for valor, n in rachas + [[False, 0]]:
        if valor:
            largo = largo + n if previo else n
        elif previo:
            golpes += largo >= minimo
        previo = valor
    return golpes

def interjeccion_aceptable(audio: np.ndarray, sr: int, hueco_s: float, palabras: int) -> tuple[bool, str]:
    """¿Sirve esta interjección sintetizada? Devuelve (sí/no, motivo).

    Se rechaza si su duración no encaja con el hueco o si suena a palabra leída (más golpes de
    voz que interjecciones tiene el texto).
    """
    dur = len(audio) / sr
    if dur < 0.12:
        return False, "salió vacía"
    if dur > 1.8 * hueco_s + 0.15:
        return False, f"muy larga ({dur:.1f}s para un hueco de {hueco_s:.1f}s)"
    if dur < 0.4 * hueco_s:
        return False, f"muy corta ({dur:.1f}s para un hueco de {hueco_s:.1f}s)"
    golpes = contar_golpes_de_voz(audio, sr)
    if golpes > palabras + 1:
        return False, f"suena a texto leído ({golpes} golpes de voz para {palabras} interjecciones)"
    return True, "ok"

# ---------- Interfaz ----------

class Sintetizador(ABC):
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or obtener_config()

    @abstractmethod
    def generar_frases(self, frases: list[dict], referencia: Path, idioma: str) -> list[tuple[np.ndarray, int]]:
        """Devuelve, por cada frase, (audio mono float32, frecuencia). Debe liberar la GPU al terminar."""

    def _acortar_desbordes(self, letra: dict, letra_json: Path, nuevas: list[int], audios: list,
                           referencia: Path, idioma: str, total_s: float, acortar) -> list:
        """MusicAI: los versos que ni al tempo máximo caben en su espacio se piden más cortos al LLM y se
        vuelven a sintetizar. Se queda la toma nueva solo si dura menos. Actualiza letra.json con el texto
        que de verdad se canta."""
        from app.pipeline.translate import contar_silabas

        cfg, frases = self.cfg, letra["frases"]
        pedidos = []
        for k, i in enumerate(nuevas):
            audio, sr = audios[k]
            dur = len(recortar_silencio(np.asarray(audio, dtype=np.float32), sr, cfg.recorte_umbral)) / sr
            espacio = espacio_disponible(frases, i, total_s)
            if dur / cfg.tempo_max <= espacio + 0.05:
                continue
            silabas = contar_silabas(frases[i]["texto"], idioma)
            objetivo = max(2, int(silabas * espacio * cfg.tempo_max / dur * 0.9))
            if objetivo >= silabas:
                continue
            pedidos.append({"i": i, "k": k, "texto": frases[i]["texto"], "original": frases[i].get("original", ""),
                            "silabas": objetivo, "segundos": frases[i]["fin"] - frases[i]["inicio"], "dur": dur})
        if not pedidos:
            return audios
        log.info("%d versos no caben ni a tempo %.2f: se piden más cortos al LLM", len(pedidos), cfg.tempo_max)
        textos = acortar(letra, pedidos)
        cambiar = [p for p in pedidos if textos.get(p["i"])]
        if not cambiar:
            return audios
        nuevos = self.generar_frases([{"texto": textos[p["i"]]} for p in cambiar], referencia, idioma)
        usados = 0
        for p, (audio, sr) in zip(cambiar, nuevos):
            dur = len(recortar_silencio(np.asarray(audio, dtype=np.float32), sr, cfg.recorte_umbral)) / sr
            if dur < p["dur"]:
                log.info("verso %d acortado: «%s» → «%s» (%.1fs → %.1fs)", p["i"] + 1, p["texto"],
                         textos[p["i"]], p["dur"], dur)
                audios[p["k"]] = (audio, sr)
                frases[p["i"]]["texto"] = textos[p["i"]]
                usados += 1
        if usados:  # el letra.json entregado debe decir lo que se canta
            Path(letra_json).write_text(json.dumps(letra, ensure_ascii=False, indent=2), encoding="utf-8")
        return audios

    def sintetizar(self, letra_json: Path, voz_original: Path, wav_salida: Path, acortar=None) -> Path:
        """letra traducida + voz original → pista de voz nueva, alineada con los tiempos de cada frase.

        acortar (opcional, MusicAI): función (letra, pedidos) → {i: texto más corto}; si se da, los versos
        que no caben en su tiempo se reescriben más cortos antes de recurrir a acelerar o recortar.
        """
        cfg = self.cfg
        letra = json.loads(Path(letra_json).read_text(encoding="utf-8"))
        frases, idioma = letra["frases"], letra["idioma_destino"]
        wav_salida = Path(wav_salida)
        tmp = wav_salida.parent / "frases"
        tmp.mkdir(parents=True, exist_ok=True)

        info = sf.info(str(voz_original))
        # misma duración que la voz original, para que la mezcla no alargue el video
        pista = np.zeros(round(info.frames / info.samplerate * FRECUENCIA), dtype=np.float32)
        # interjecciones (oh, hey...): según INTERJECCIONES se copian del original o se sintetizan
        modo = cfg.interjecciones
        if modo not in MODOS_INTERJECCIONES:
            raise ErrorPipeline(f"INTERJECCIONES={modo} no existe (válidos: {', '.join(MODOS_INTERJECCIONES)})")
        total_s = len(pista) / FRECUENCIA
        conservadas = [i for i, f in enumerate(frases) if f.get("conservar")]
        nuevas = [i for i, f in enumerate(frases) if not f.get("conservar") and f["texto"].strip()]
        cantadas = [frases[i] for i in nuevas]
        # se dicen en el idioma original (así "ooh" o "hey" se pronuncian como en la canción)
        idioma_interj = letra.get("idioma_origen") if letra.get("idioma_origen") in IDIOMAS_XTTS else idioma
        gritos = [] if modo == "original" else [
            {"texto": escribir_interjeccion(frases[i]["texto"], frases[i]["fin"] - frases[i]["inicio"]),
             "idioma": idioma_interj} for i in conservadas]
        audios = []
        if cantadas or gritos:
            referencia = preparar_referencia(voz_original, cantadas or frases, tmp / "referencia.wav")
            audios = self.generar_frases(cantadas + gritos, referencia, idioma)
            if acortar is not None and cfg.acortar_desbordes and cantadas:
                audios = self._acortar_desbordes(letra, letra_json, nuevas, audios, referencia, idioma,
                                                 total_s, acortar)

        log.info("ajuste de duración con %s", "rubberband" if tiene_filtro("rubberband", cfg)
                 else "atempo (rubberband no está en FFmpeg: más metálico al acelerar)")
        niveles = []  # volumen de cada verso sintetizado: referencia para igualar las interjecciones
        informe = []  # MusicAI: qué se hizo con cada verso (se guarda junto a las frases para depurar)
        fin_anterior = 0  # muestra donde termina el verso colocado antes (puede invadir el hueco siguiente)
        for i, (audio, sr) in zip(nuevas, audios):
            frase = frases[i]
            audio = recortar_silencio(np.asarray(audio, dtype=np.float32), sr, cfg.recorte_umbral, 0.04)
            if audio.size == 0:
                informe.append({"verso": i + 1, "accion": "vacío"})
                continue
            ventana = frase["fin"] - frase["inicio"]
            tempo = calcular_tempo(audio.size / sr, ventana, cfg.tempo_min, cfg.tempo_max)
            crudo, ajustado = tmp / f"{i:03d}_crudo.wav", tmp / f"{i:03d}.wav"
            sf.write(str(crudo), audio, sr, subtype="PCM_16")
            ajustar_duracion(crudo, ajustado, tempo, cfg)
            voz, _ = sf.read(str(ajustado), dtype="float32")
            inicio = int(frase["inicio"] * FRECUENCIA)
            maximo = int(espacio_disponible(frases, i, total_s) * FRECUENCIA)
            datos = {"verso": i + 1, "texto": frase["texto"], "ventana_s": round(ventana, 2),
                     "sintetizado_s": round(audio.size / sr, 2), "tempo": round(tempo, 3), "accion": "cabe"}
            if voz.size > maximo > 0:
                # MusicAI: antes de recortar se intenta conservar la frase entera
                # 1) un poco más de velocidad (solo para no cortar palabras)
                rescate = min(cfg.tempo_rescate, (audio.size / sr) / (maximo / FRECUENCIA))
                if rescate > tempo + 0.01:
                    ajustar_duracion(crudo, ajustado, rescate, cfg)
                    voz, _ = sf.read(str(ajustado), dtype="float32")
                    datos.update(tempo=round(rescate, 3), accion="tempo_rescate")
                # 2) empezar un poco antes, dentro del silencio que deja el verso anterior
                if voz.size > maximo:
                    libre = inicio - fin_anterior - int(0.05 * FRECUENCIA)
                    adelanto = max(0, min(int(cfg.adelanto_max_s * FRECUENCIA), libre, voz.size - maximo))
                    if adelanto > 0:
                        inicio -= adelanto
                        maximo += adelanto
                        datos.update(adelanto_s=round(adelanto / FRECUENCIA, 2), accion="adelantado")
                # 3) último recurso: cortar, a ser posible en una pausa entre palabras
                if voz.size > maximo:
                    corte = punto_de_corte(voz, maximo)
                    perdido = (voz.size - (corte or maximo)) / FRECUENCIA
                    log.warning("frase %d no cabe (%.1fs en %.1fs): %s, se pierden %.2fs", i + 1,
                                voz.size / FRECUENCIA, maximo / FRECUENCIA,
                                "cortada en una pausa entre palabras" if corte else "cortada a mitad de palabra",
                                perdido)
                    voz = voz[: corte or maximo].copy()
                    cola = min(len(voz), int((0.03 if corte else 0.08) * FRECUENCIA))
                    voz[-cola:] *= np.linspace(1.0, 0.0, cola, dtype=np.float32)
                    datos.update(accion="cortada_en_pausa" if corte else "cortada_a_mitad", perdido_s=round(perdido, 2))
            informe.append(datos)
            voz = voz[: max(0, len(pista) - inicio)]
            pista[inicio: inicio + len(voz)] += voz
            fin_anterior = inicio + len(voz)
            niveles.append(nivel_voz(voz))
        if informe:
            acciones = {}
            for d in informe:
                acciones[d["accion"]] = acciones.get(d["accion"], 0) + 1
            log.info("colocación de versos: %s", ", ".join(f"{k}={v}" for k, v in sorted(acciones.items())))
            (tmp / "informe_versos.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")

        if conservadas:
            objetivo = float(np.median(niveles)) if niveles else 0.0
            original = leer_mono(voz_original)
            usadas = {"sintetizada": 0, "original": 0}
            for k, i in enumerate(conservadas):
                a, b = tramo_interjeccion(frases, i, min(total_s, len(original) / FRECUENCIA))
                if b - a < 0.02:
                    continue
                clip, desde = None, a
                if gritos:
                    audio, sr = audios[len(cantadas) + k]
                    audio = recortar_silencio(np.asarray(audio, dtype=np.float32), sr)
                    hueco = b - frases[i]["inicio"]
                    palabras = max(1, len(gritos[k]["texto"].split()))
                    vale, motivo = interjeccion_aceptable(audio, sr, hueco, palabras)
                    log.info("interjección %d «%s»: %.2fs sintetizados para un hueco de %.2fs → %s", i + 1,
                             gritos[k]["texto"], audio.size / sr, hueco, motivo)
                    if modo == "sintetizada" and audio.size == 0:
                        vale = False  # no hay nada que colocar: único caso en que se usa la original
                    elif modo == "sintetizada":
                        vale = True
                    if vale:
                        # se ajusta al hueco sin forzarla: poco margen de velocidad y, si sobra, se recorta
                        tempo = calcular_tempo(audio.size / sr, hueco, cfg.interj_tempo_min, cfg.interj_tempo_max)
                        crudo, ajustado = tmp / f"interj_{i:03d}_crudo.wav", tmp / f"interj_{i:03d}.wav"
                        sf.write(str(crudo), audio, sr, subtype="PCM_16")
                        ajustar_duracion(crudo, ajustado, tempo, cfg)
                        clip, _ = sf.read(str(ajustado), dtype="float32")
                        clip, desde = clip[: int(hueco * FRECUENCIA)], frases[i]["inicio"]
                        usadas["sintetizada"] += 1
                    else:
                        log.info("interjección %d (%s): %s → se usa la voz original", i + 1,
                                 gritos[k]["texto"], motivo)
                if clip is None:
                    clip = original[int(a * FRECUENCIA): int(b * FRECUENCIA)]
                    usadas["original"] += 1
                clip = fundir_bordes(igualar_volumen(clip, objetivo))
                inicio = int(desde * FRECUENCIA)
                clip = clip[: max(0, len(pista) - inicio)]
                pista[inicio: inicio + len(clip)] += clip
            log.info("interjecciones (modo %s): %d sintetizadas, %d de la voz original", modo,
                     usadas["sintetizada"], usadas["original"])
        sf.write(str(wav_salida), np.clip(pista, -1.0, 1.0), FRECUENCIA, subtype="PCM_16")
        return wav_salida


# ---------- Implementaciones ----------

class XttsSintetizador(Sintetizador):
    def generar_frases(self, frases, referencia, idioma):
        cfg = self.cfg
        if idioma not in IDIOMAS_XTTS:
            raise ErrorPipeline(f"XTTS-v2 no soporta el idioma '{idioma}'")
        idioma_base = idioma
        preparar_entorno_modelos(cfg)
        import torch
        from TTS.api import TTS

        dispositivo = cfg.dispositivo if torch.cuda.is_available() else "cpu"
        tts = TTS(model_name=cfg.xtts_modelo, progress_bar=False).to(dispositivo)
        modelo = tts.synthesizer.tts_model
        sr = modelo.config.audio.output_sample_rate
        try:
            # el timbre se calcula una sola vez y se reutiliza en todas las frases
            gpt_latente, hablante = modelo.get_conditioning_latents(audio_path=[str(referencia)])
            audios = []
            def generar(texto: str, idioma: str) -> np.ndarray:
                salida = modelo.inference(texto, IDIOMAS_XTTS[idioma], gpt_latente, hablante,
                                          temperature=0.65, enable_text_splitting=True)
                wav = salida["wav"]
                if hasattr(wav, "detach"):
                    wav = wav.detach().cpu().numpy()
                return np.asarray(wav, dtype=np.float32).reshape(-1)

            for n, frase in enumerate(frases, start=1):
                # XTTS a veces se desboca y genera varios segundos de más (repite o balbucea):
                # si la duración no cuadra con el texto, se repite y se queda la toma más corta
                idioma = frase.get("idioma", idioma_base)  # una frase puede pedir otro idioma
                tope = duracion_maxima_esperada(frase["texto"], idioma)
                wav = generar(frase["texto"], idioma)
                for _ in range(cfg.xtts_reintentos):
                    if len(recortar_silencio(wav, sr)) / sr <= tope:
                        break
                    log.info("frase %d: XTTS generó %.1fs para un texto de ~%.1fs; se repite", n,
                             len(recortar_silencio(wav, sr)) / sr, tope)
                    otra = generar(frase["texto"], idioma)
                    if len(recortar_silencio(otra, sr)) < len(recortar_silencio(wav, sr)):
                        wav = otra
                audios.append((wav, sr))
        finally:
            del modelo, tts
            liberar_vram()
        return audios


class RvcSintetizador(Sintetizador):
    """Pendiente (fase 7): convertir una guía cantada al timbre original con RVC."""

    def generar_frases(self, frases, referencia, idioma):
        raise ErrorPipeline("SINTETIZADOR=rvc aún no está implementado; usa SINTETIZADOR=xtts")


SINTETIZADORES = {"xtts": XttsSintetizador, "rvc": RvcSintetizador}


def crear_sintetizador(cfg: Config | None = None) -> Sintetizador:
    cfg = cfg or obtener_config()
    if cfg.sintetizador not in SINTETIZADORES:
        raise ErrorPipeline(f"SINTETIZADOR={cfg.sintetizador} no existe (válidos: {', '.join(SINTETIZADORES)})")
    return SINTETIZADORES[cfg.sintetizador](cfg)


def sintetizar(letra_json: Path, voz_original: Path, wav_salida: Path, cfg: Config | None = None,
               acortar=None) -> Path:
    return crear_sintetizador(cfg).sintetizar(letra_json, voz_original, wav_salida, acortar=acortar)
