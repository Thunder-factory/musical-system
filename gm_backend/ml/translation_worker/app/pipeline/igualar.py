"""Etapa 5c (fase 7, paso 2) — que la voz nueva suene «dentro» de la canción como la original.

Tres ajustes, todos medidos sobre la voz original separada (sin modelos ni GPU):
  1. Ecualización: el espectro medio de la voz nueva se lleva al de la original (filtro FIR de fase lineal,
     por bandas de 1/3 de octava y con un tope de ±IGUALAR_EQ_MAX_DB para no exagerar).
  2. Reverberación: se estima cuánto dura la cola de la voz original (RT60) y se añade una reverb
     sintética de esa duración, con la proporción IGUALAR_REVERB_MEZCLA.
  3. Nivel: el volumen de la voz nueva donde suena se iguala al de la original, para que la relación
     voz/instrumental sea la de la canción.
"""
import logging
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from app.config import Config, obtener_config

log = logging.getLogger("worker.igualar")

N_FFT = 4096


def _mono(x: np.ndarray) -> np.ndarray:
    return x.mean(axis=1) if x.ndim == 2 else x


def tramos_con_voz(x: np.ndarray, sr: int, umbral_db: float = -35.0, ventana_s: float = 0.05) -> np.ndarray:
    """Máscara por muestra: True donde la voz suena (más de umbral_db respecto al tramo más fuerte)."""
    n = max(1, int(ventana_s * sr))
    k = len(x) // n
    if k == 0:
        return np.zeros(len(x), dtype=bool)
    rms = np.sqrt(np.mean(x[: k * n].reshape(k, n) ** 2, axis=1)) + 1e-9
    fuerte = np.percentile(rms, 95)
    activa = 20 * np.log10(rms / fuerte) > umbral_db
    mascara = np.repeat(activa, n)
    return np.pad(mascara, (0, len(x) - len(mascara)))


def espectro_medio(x: np.ndarray, sr: int, mascara: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Espectro de potencia medio (Welch) de los tramos con voz."""
    sonido = x[mascara] if mascara.sum() > N_FFT else x
    f, p = signal.welch(sonido, sr, nperseg=N_FFT)
    return f, p + 1e-12


def curva_eq(f: np.ndarray, p_nueva: np.ndarray, p_original: np.ndarray, max_db: float,
             f_min: float = 80.0, f_max: float = 16000.0) -> np.ndarray:
    """Ganancia en dB por frecuencia que lleva p_nueva a p_original, suavizada en 1/3 de octava.

    Fuera de [f_min, f_max] no se toca (0 dB): ahí casi no hay voz y solo se subiría ruido.
    El nivel global se quita (la ganancia media es 0): el volumen se ajusta aparte.
    """
    dif = 10 * np.log10(p_original / p_nueva)
    suave = np.zeros_like(dif)
    for i, fc in enumerate(f):
        if fc < f_min or fc > f_max:
            continue
        banda = (f >= fc / 2 ** (1 / 6)) & (f <= fc * 2 ** (1 / 6))
        suave[i] = dif[banda].mean()
    dentro = (f >= f_min) & (f <= f_max)
    if dentro.any():
        suave[dentro] -= np.average(suave[dentro], weights=p_original[dentro])
    return np.clip(suave, -max_db, max_db) * dentro


def aplicar_eq(x: np.ndarray, sr: int, f: np.ndarray, ganancia_db: np.ndarray, taps: int = 2047) -> np.ndarray:
    """Filtro FIR de fase lineal con esa curva (se compensa el retardo: no desplaza la voz)."""
    fir = signal.firwin2(taps, f / (sr / 2), 10 ** (ganancia_db / 20))
    return signal.fftconvolve(x, fir, mode="full")[taps // 2: taps // 2 + len(x)]


def estimar_rt60(x: np.ndarray, sr: int, min_s: float = 0.15, max_s: float = 2.5) -> float:
    """Cuánto tarda la voz original en apagarse 60 dB tras cortar una frase (mediana de varias colas).

    Un final de frase es un punto fuerte después del cual la envolvente solo baja (caída libre) al menos
    8 dB en 500 ms. Se ajusta una recta a esa caída (en dB, hasta 40 dB por debajo del inicio).
    """
    n = int(0.01 * sr)
    k = len(x) // n
    ventana = 50  # 500 ms
    if k < 2 * ventana:
        return min_s
    env = 20 * np.log10(np.sqrt(np.mean(x[: k * n].reshape(k, n) ** 2, axis=1)) + 1e-6)
    tope = np.percentile(env, 95)
    pendientes, siguiente = [], 0
    for i in range(k - ventana):
        if i < siguiente or env[i] < tope - 12:
            continue
        tramo = env[i: i + ventana]
        if tramo[1:].max() >= tramo[0] or tramo[-1] > tramo[0] - 8:
            continue  # no es caída libre (sigue la nota o empieza otra)
        # Una cola real baja poco a poco (incluso con RT60 de 0.15 s son ~4 dB cada 10 ms). Un salto de
        # más de 12 dB en un cuadro es el corte del sonido directo: la reverb, si la hay, es lo que queda
        # debajo, así que se mide desde ahí.
        # (los saltos que caen al silencio, más de 40 dB abajo, son el final de la cola, no el corte)
        saltos = np.where(tramo[1:] > tramo[0] - 40, np.diff(tramo), 0.0)
        j = int(np.argmin(saltos))
        cola = tramo[j + 1:] if saltos[j] < -12 else tramo
        util = cola[cola > cola[0] - 40]
        if len(util) < 10 or util[0] - util.min() < 10 or np.diff(util).min() < -12:
            pendientes.append(-600.0)  # nada que decaiga gradualmente: voz seca
        else:
            bloques = [b.mean() for b in np.array_split(util, max(2, len(util) // 10))]
            if any(b2 > b1 - 1.0 for b1, b2 in zip(bloques, bloques[1:])):
                continue  # meseta y luego corte (fin de una nota sin reverb), no una cola
            pendientes.append(np.polyfit(np.arange(len(util)) * 0.01, util, 1)[0])  # dB por segundo
        siguiente = i + ventana
    if len(pendientes) < 3:
        return min_s
    return float(np.clip(-60.0 / np.median(pendientes), min_s, max_s))


def reverb_sintetica(rt60: float, sr: int, semilla: int = 0) -> np.ndarray:
    """Respuesta al impulso de ruido con caída exponencial (pierde 60 dB en rt60 segundos), algo oscura."""
    azar = np.random.default_rng(semilla)
    n = int(rt60 * sr)
    t = np.arange(n) / sr
    ir = azar.standard_normal(n) * 10 ** (-3 * t / rt60)
    ir = signal.sosfilt(signal.butter(2, 6000, "low", fs=sr, output="sos"), ir)  # las salas apagan los agudos
    ir[: int(0.01 * sr)] *= np.linspace(0, 1, int(0.01 * sr))  # sin golpe al inicio
    return ir / np.sqrt(np.sum(ir ** 2))


def nivel_db(x: np.ndarray, mascara: np.ndarray) -> float:
    sonido = x[mascara] if mascara.any() else x
    return 20 * np.log10(np.sqrt(np.mean(sonido ** 2)) + 1e-9)


def curva_nivel_por_frase(x: np.ndarray, o: np.ndarray, sr: int, frases: list[dict], max_db: float = 6.0,
                          rampa_s: float = 0.05) -> tuple[np.ndarray, list[float]]:
    """MusicAI: ganancia por muestra para que cada verso tenga, respecto a los demás, el volumen que tiene en
    la canción original (XTTS y Seed-VC dan volúmenes distintos de un verso a otro).

    Solo corrige diferencias RELATIVAS (la mediana de las correcciones es 0 dB; el nivel global lo ajusta
    igualar_voz después) y con tope ±max_db. Dentro de cada verso la ganancia es constante; entre versos
    cambia con una rampa lineal (como mínimo `rampa_s`), así no hay saltos bruscos.
    Devuelve (ganancia lineal por muestra, correcciones en dB por verso medido).
    """
    tiempos, ganancias = [], []
    m_x, m_o = tramos_con_voz(x, sr), tramos_con_voz(o, sr)
    for f in sorted(frases, key=lambda f: f["inicio"]):
        a, b = int(f["inicio"] * sr), int(f["fin"] * sr)
        if b - a < int(0.2 * sr) or b > len(x) or b > len(o):
            continue
        if m_x[a:b].sum() < 0.1 * sr or m_o[a:b].sum() < 0.1 * sr:
            continue  # sin voz en alguna de las dos: no hay nada que comparar
        dif = nivel_db(o[a:b], m_o[a:b]) - nivel_db(x[a:b], m_x[a:b])
        tiempos.append((f["inicio"], f["fin"]))
        ganancias.append(dif)
    if not ganancias:
        return np.ones(len(x)), []
    g = np.asarray(ganancias)
    g = np.clip(g - np.median(g), -max_db, max_db)
    puntos_t, puntos_g = [], []
    for (a, b), gi in zip(tiempos, g):
        r = min(rampa_s / 2, (b - a) / 4)
        puntos_t += [a + r, b - r]
        puntos_g += [gi, gi]
    curva_db = np.interp(np.arange(len(x)) / sr, puntos_t, puntos_g)
    return 10 ** (curva_db / 20), [round(float(v), 1) for v in g]


def igualar_voz(voz_nueva: Path, voz_original: Path, wav_salida: Path, cfg: Config | None = None,
                frases: list[dict] | None = None) -> Path:
    """voz nueva + voz original separada → voz nueva con la ecualización, reverb y nivel de la original.

    frases (opcional, MusicAI): versos con sus tiempos; con IGUALAR_NIVEL_POR_FRASE cada verso se lleva al
    volumen relativo que tiene en la original.
    """
    cfg = cfg or obtener_config()
    nueva, sr = sf.read(str(voz_nueva), dtype="float32", always_2d=True)
    original, sr_o = sf.read(str(voz_original), dtype="float32", always_2d=True)
    x, o = _mono(nueva).astype(np.float64), _mono(original).astype(np.float64)
    if sr_o != sr:
        o = signal.resample_poly(o, sr, sr_o)
    m_x, m_o = tramos_con_voz(x, sr), tramos_con_voz(o, sr)

    f, p_x = espectro_medio(x, sr, m_x)
    _, p_o = espectro_medio(o, sr, m_o)
    curva = curva_eq(f, p_x, p_o, cfg.igualar_eq_max_db)
    y = aplicar_eq(x, sr, f, curva)

    correcciones: list[float] = []
    if frases and cfg.igualar_nivel_por_frase:  # antes de la reverb: así la cola sigue al verso
        n = min(len(y), len(o))
        ganancia_frases, correcciones = curva_nivel_por_frase(y[:n], o[:n], sr, frases, cfg.igualar_nivel_max_db)
        y[:n] *= ganancia_frases

    rt60 = estimar_rt60(o, sr)
    if cfg.igualar_reverb_mezcla > 0:
        cola = signal.fftconvolve(y, reverb_sintetica(rt60, sr))[: len(y)]
        cola *= np.sqrt(np.mean(y ** 2)) / (np.sqrt(np.mean(cola ** 2)) + 1e-12)  # mismo nivel que la voz seca
        y = (1 - cfg.igualar_reverb_mezcla) * y + cfg.igualar_reverb_mezcla * cola

    ganancia = nivel_db(o, m_o) - nivel_db(y, tramos_con_voz(y, sr))  # medidas iguales: las dos con su cola
    y *= 10 ** (np.clip(ganancia, -12, 12) / 20)
    pico = np.abs(y).max()
    if pico > 0.98:  # sin recortes
        y *= 0.98 / pico
    wav_salida = Path(wav_salida)
    wav_salida.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(wav_salida), y.astype(np.float32), sr, subtype="PCM_16")
    log.info("igualar: EQ ±%.1f dB (máx. aplicado %.1f dB), RT60 original %.2f s, reverb %.0f %%, nivel %+.1f dB",
             cfg.igualar_eq_max_db, float(np.abs(curva).max()), rt60, 100 * cfg.igualar_reverb_mezcla, ganancia)
    if correcciones:
        log.info("igualar: nivel por verso en %d versos (corrección máx. %.1f dB, %d con más de 3 dB)",
                 len(correcciones), max(abs(c) for c in correcciones), sum(abs(c) > 3 for c in correcciones))
    return wav_salida
