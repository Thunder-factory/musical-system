"""
Etapa 5 del pipeline: ANÁLISIS MUSICAL.

Entiende la melodía tarareada: a qué tempo se cantó, en qué tonalidad está y
dónde cae cada nota en una grilla de pulsos. No identifica ninguna canción
existente: describe lo que se cantó para que las etapas siguientes generen
ritmo (la batería necesita el tempo) y armonía (los acordes necesitan la
tonalidad) coherentes con esa melodía.

Las tres partes son reglas explicables, sin modelos:

1. TEMPO: se prueban todos los tempos del rango y se elige el que mejor
   alinea los ONSETS DE LAS NOTAS LIMPIAS a una grilla de corcheas. Un
   tarareo no tiene percusión, así que el beat tracking sobre el audio
   (librosa) falla seguido: se usa solo como segunda opinión.
2. TONALIDAD: Krumhansl-Schmuckler (music21) sobre las notas ponderadas por
   duración, para que una nota de paso no cambie la tonalidad.
3. CUANTIZACIÓN SUAVE: una nota se ajusta a la grilla de semicorcheas solo si
   ya estaba cerca. Si no, se respeta como se cantó. El timing original en
   segundos sigue en `melodia`, para que el render no suene robótico.
"""

from __future__ import annotations

import logging
import math
from itertools import pairwise
from pathlib import Path

import numpy as np

from app.modelos import AnalisisMusical, MotivoFallo, NotaCuantizada, NotaMusical
from app.pipeline.excepciones import ErrorAudioInvalido

logger = logging.getLogger(__name__)

PASO_BPM = 0.25
# Bonus al candidato que coincide con librosa (±4 %): desempata, no manda.
BONUS_COINCIDE_LIBROSA = 1.25
TOLERANCIA_COINCIDENCIA_LIBROSA = 0.04
# Qué tan estricta es la preferencia de "una nota ≈ un pulso" (en octavas).
DESVIO_DENSIDAD_OCTAVAS = 0.5
SEMICORCHEAS_POR_PULSO = 4
COMPAS_POR_DEFECTO = "4/4"

RITMO_MEDIDO = "medido"
RITMO_LIBRE = "libre"
SIMULACIONES_AZAR = 60
# Valores musicales (en tiempos) a los que se lleva un tarareo en tiempo libre:
# semicorchea, corchea, corchea con puntillo, negra, negra con puntillo,
# blanca, blanca con puntillo, redonda.
VALORES_RITMICOS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
# Una distancia entre notas es "pausa entre frases" si supera 2.5 veces la
# típica y 1.5 s. Medido en el lote real: las pausas van de 1.8 a 5.7 s.
UMBRAL_PAUSA_RELATIVO = 2.5
PAUSA_MINIMA_SEGUNDOS = 1.5


# ----------------------------------------------------------------------------
# Tempo
# ----------------------------------------------------------------------------

def _alineacion(onsets: np.ndarray, celdas: np.ndarray, pesos: np.ndarray | None = None) -> np.ndarray:
    """
    Qué tan bien caen los onsets en una grilla de período `celda`, para cada celda.

    Cada onset se convierte en un ángulo (su posición dentro de la celda) y se
    promedian los vectores: si todos caen en el mismo punto de la grilla, el
    promedio mide 1; si están desparramados, tiende a 0. No hace falta buscar
    la fase de la grilla: el promedio la encuentra solo (su ángulo).
    Devuelve el vector complejo promedio: módulo = alineación, ángulo = fase.
    """
    angulos = 2.0 * np.pi * onsets[None, :] / celdas[:, None]
    vectores = np.exp(1j * angulos)
    if pesos is None:
        return vectores.mean(axis=1)
    return (vectores * pesos[None, :]).sum(axis=1) / pesos.sum()


def _densidad(onsets: np.ndarray, candidatos: np.ndarray) -> np.ndarray:
    """
    Preferencia por el tempo en el que la nota típica dura alrededor de un pulso.

    La alineación sola no distingue entre leer un ritmo a 66 o a 132 BPM (ni
    a 99, en tresillos): las mismas notas encajan perfecto en las tres
    grillas. Lo que decide cuál es el pulso que se siente es cuántas notas
    caen por pulso: en una melodía cantada, la nota típica dura entre una
    corchea y una negra. Dentro de esa franja no hay penalización; fuera,
    cae suave. Medido con melodías sintéticas: sin este factor, 39 de 180
    casos (jitter 0-20 ms) quedaban en ×2, ×½ o ×1.5 del tempo real.
    """
    if len(onsets) < 2:
        return np.ones_like(candidatos)
    mediana_ioi = float(np.median(np.diff(onsets)))
    if mediana_ioi <= 0:
        return np.ones_like(candidatos)
    octavas = np.log2(mediana_ioi * candidatos / 60.0)  # 0 = negra, -1 = corchea
    fuera_de_franja = np.where(octavas > 0, octavas, np.where(octavas < -1, -1 - octavas, 0.0))
    return np.exp(-0.5 * (fuera_de_franja / DESVIO_DENSIDAD_OCTAVAS) ** 2)


def _plegar_al_rango(bpm: float, minimo: float, maximo: float) -> float:
    """Lleva un tempo al rango duplicando o dividiendo por 2 (el mismo pulso, otra lectura)."""
    while bpm > maximo:
        bpm /= 2.0
    while bpm < minimo:
        bpm *= 2.0
    return bpm


def estimar_bpm(
    onsets: list[float] | np.ndarray,
    config,
    bpm_librosa: float | None = None,
) -> tuple[float, float]:
    """
    Devuelve (bpm, confianza 0-1).

    puntaje(bpm) = alineación de los onsets a la grilla de corcheas
                   × preferencia suave por tempos cercanos a analisis_bpm_preferido
                   × bonus si coincide con librosa.

    Por qué corcheas: es la subdivisión más común de una melodía cantada.
    Una grilla más fina "acepta" cualquier cosa; una más gruesa rechaza
    melodías con corcheas. La preferencia de tempo existe porque un tarareo
    en 60 y en 120 encaja igual de bien en la grilla: es la misma música
    leída a otra escala, y hace falta un criterio para elegir.
    """
    onsets = np.sort(np.asarray(onsets, dtype=np.float64))
    candidatos = np.arange(config.analisis_bpm_minimo, config.analisis_bpm_maximo + PASO_BPM / 2, PASO_BPM)
    celdas_corchea = 30.0 / candidatos

    alineacion = np.abs(_alineacion(onsets, celdas_corchea))
    preferencia = np.exp(-0.5 * np.log2(candidatos / config.analisis_bpm_preferido) ** 2)
    puntaje = alineacion * preferencia * _densidad(onsets, candidatos)

    if bpm_librosa:
        referencia = _plegar_al_rango(bpm_librosa, config.analisis_bpm_minimo, config.analisis_bpm_maximo)
        coincide = np.abs(candidatos / referencia - 1.0) <= TOLERANCIA_COINCIDENCIA_LIBROSA
        puntaje = np.where(coincide, puntaje * BONUS_COINCIDE_LIBROSA, puntaje)

    mejor = int(np.argmax(puntaje))
    return float(candidatos[mejor]), float(alineacion[mejor])


def estimar_pulso_cero(onsets: np.ndarray, duraciones: np.ndarray, bpm: float, tolerancia: float) -> float:
    """
    Segundo del audio donde cae el pulso 0 de la grilla.

    La grilla de corcheas ya tiene fase (el ángulo del promedio), pero hay dos
    corcheas por pulso: ¿cuál de las dos es "el tiempo"? Se elige la que
    queda más cerca de la fase de las notas LARGAS (ponderando por duración),
    porque las notas largas suelen caer en el tiempo y las cortas entre
    tiempos. Después se toma el pulso de esa grilla en o justo antes de la
    primera nota.
    """
    pulso = 60.0 / bpm
    corchea = pulso / 2.0

    fase_corchea = (np.angle(_alineacion(onsets, np.array([corchea]))[0]) / (2 * np.pi)) % 1.0 * corchea
    fase_pulso_notas_largas = (
        np.angle(_alineacion(onsets, np.array([pulso]), duraciones)[0]) / (2 * np.pi)
    ) % 1.0 * pulso

    def distancia_circular(a: float, b: float) -> float:
        d = abs(a - b) % pulso
        return min(d, pulso - d)

    fase = min((fase_corchea, fase_corchea + corchea), key=lambda f: distancia_circular(f, fase_pulso_notas_largas))

    # Pulso de la grilla en o antes de la primera nota. Si la primera nota
    # cae apenas antes de un pulso (dentro de la tolerancia de cuantización),
    # ese pulso es el 0: la nota se adelantó, no es un pulso anterior.
    tolerancia_pulsos = tolerancia / SEMICORCHEAS_POR_PULSO
    k = math.floor((onsets[0] - fase) / pulso + tolerancia_pulsos)
    return float(fase + k * pulso)


def tempo_librosa(ruta_wav: Path) -> float | None:
    """Segunda opinión: beat tracking de librosa sobre el audio. None si no da nada útil."""
    try:
        import librosa

        audio, sr = librosa.load(str(ruta_wav), sr=None, mono=True)
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        valor = float(np.atleast_1d(tempo)[0])
        return valor if valor > 0 else None
    except Exception:
        logger.warning("librosa no pudo estimar el tempo; se sigue solo con las notas", exc_info=True)
        return None


# ----------------------------------------------------------------------------
# Tonalidad
# ----------------------------------------------------------------------------

def estimar_tonalidad(notas: list[NotaMusical]) -> tuple[str, float]:
    """
    Devuelve (tonalidad, correlación), p. ej. ("G major", 0.83).

    Se llama a KrumhanslSchmuckler explícitamente: el `analyze('key')` por
    defecto de music21 usa otro perfil (Aarden-Essen). Las duraciones van
    como quarterLength porque music21 pondera la distribución de clases de
    altura por duración; la unidad no importa, solo la proporción.
    """
    from music21 import note, stream
    from music21.analysis.discrete import KrumhanslSchmuckler

    flujo = stream.Stream()
    for n in notas:
        flujo.append(note.Note(midi=n.nota, quarterLength=max(round(n.duracion * 16) / 16, 1 / 16)))

    tonalidad = KrumhanslSchmuckler().getSolution(flujo)
    nombre = f"{tonalidad.tonic.name.replace('-', 'b')} {tonalidad.mode}"
    return nombre, float(tonalidad.correlationCoefficient)


# ----------------------------------------------------------------------------
# Cuantización suave
# ----------------------------------------------------------------------------

def _ajustar(valor_pulsos: float, tolerancia: float) -> tuple[float, bool]:
    """Ajusta a la semicorchea más cercana solo si está a menos de `tolerancia` de celda."""
    objetivo = round(valor_pulsos * SEMICORCHEAS_POR_PULSO) / SEMICORCHEAS_POR_PULSO
    if abs(valor_pulsos - objetivo) <= tolerancia / SEMICORCHEAS_POR_PULSO:
        return objetivo, True
    return valor_pulsos, False


def cuantizar(notas: list[NotaMusical], bpm: float, pulso_cero: float, tolerancia: float) -> list[NotaCuantizada]:
    pulso = 60.0 / bpm
    resultado: list[NotaCuantizada] = []
    for n in sorted(notas, key=lambda x: x.inicio):
        inicio_crudo = (n.inicio - pulso_cero) / pulso
        fin_crudo = inicio_crudo + n.duracion / pulso

        inicio, ajustada = _ajustar(inicio_crudo, tolerancia)
        fin, _ = _ajustar(fin_crudo, tolerancia)
        inicio = max(0.0, inicio)
        duracion = fin - inicio
        if duracion < 1 / (2 * SEMICORCHEAS_POR_PULSO):
            # El ajuste no puede hacer desaparecer una nota: si la dejó en
            # menos de una fusa, se respeta la duración cantada.
            duracion = max(n.duracion / pulso, 1 / (2 * SEMICORCHEAS_POR_PULSO))

        resultado.append(NotaCuantizada(
            nota=n.nota,
            inicioPulsos=round(inicio, 4),
            duracionPulsos=round(duracion, 4),
            velocidad=n.velocidad,
            ajustada=ajustada,
            expresion=n.expresion,
        ))
    return resultado


# ----------------------------------------------------------------------------
# ¿El tarareo tiene pulso? (comparado contra el azar)
# ----------------------------------------------------------------------------

def alineacion_por_azar(cantidad_notas: int, lapso_segundos: float, config) -> tuple[float, float]:
    """
    Qué alineación da el estimador con notas puestas AL AZAR: (promedio, percentil 95).

    La alineación cruda engaña: con pocas notas, el estimador siempre
    encuentra ALGÚN tempo donde encajan bastante bien, porque prueba 400.
    Medido con el lote real (2026-11-14): 9 notas al azar ya dan ~0.64. Por
    eso el pulso se juzga contra lo que daría el azar con la misma cantidad
    de notas en el mismo lapso. Semilla fija: mismo tarareo, misma respuesta.
    """
    rng = np.random.default_rng(1234)
    valores = [
        estimar_bpm(np.sort(rng.uniform(0.0, lapso_segundos, cantidad_notas)), config)[1]
        for _ in range(SIMULACIONES_AZAR)
    ]
    return float(np.mean(valores)), float(np.percentile(valores, 95))


# ----------------------------------------------------------------------------
# Ritmo libre: regularizar por proporciones
# ----------------------------------------------------------------------------

def _valor_ritmico(pulsos: float) -> float:
    """El valor musical más cercano, comparando proporciones (en escala logarítmica)."""
    pulsos = max(pulsos, 1e-3)
    return min(VALORES_RITMICOS, key=lambda v: abs(math.log2(pulsos / v)))


def detectar_pausas(iois: np.ndarray) -> np.ndarray:
    """
    Qué distancias entre notas son una pausa entre frases (respirar, pensar)
    y no parte del ritmo: mucho más largas que la típica y de más de 1.5 s.
    """
    mediana = float(np.median(iois))
    return (iois > UMBRAL_PAUSA_RELATIVO * mediana) & (iois > PAUSA_MINIMA_SEGUNDOS)


def tempo_por_densidad(onsets: np.ndarray, config) -> float:
    """
    Tempo cuando el tarareo no tiene pulso propio: el que hace que la nota
    típica (mediana de las distancias entre notas, sin contar las pausas entre
    frases) dure un tiempo. Se redondea a un entero y se lleva al rango.
    """
    iois = np.diff(onsets)
    sin_pausas = iois[~detectar_pausas(iois)]
    tipica = float(np.median(sin_pausas if sin_pausas.size else iois))
    bpm = _plegar_al_rango(60.0 / tipica, config.analisis_bpm_minimo, config.analisis_bpm_maximo)
    return float(round(bpm))


def regularizar(notas: list[NotaMusical], bpm: float) -> list[NotaCuantizada]:
    """
    Reescribe el ritmo de un tarareo en tiempo libre, conservando proporciones.

    Cada nota pasa a durar el valor musical más cercano a su duración
    relativa: si duró el doble que la nota típica, pasa a durar 2 tiempos.
    Se conservan las alturas, el orden y lo largo o corto de cada nota; lo
    que se pierde es la irregularidad del tiempo, que es justamente lo que
    impide ponerle batería y acordes. Una pausa entre frases se vuelve un
    silencio de 1 o 2 tiempos (no de 4 segundos).
    """
    pulso = 60.0 / bpm
    ordenadas = sorted(notas, key=lambda x: x.inicio)
    iois = np.diff([n.inicio for n in ordenadas])
    pausas = detectar_pausas(iois) if iois.size else np.array([], dtype=bool)

    resultado: list[NotaCuantizada] = []
    posicion = 0.0
    for i, n in enumerate(ordenadas):
        cantada = _valor_ritmico(n.duracion / pulso)
        if i == len(ordenadas) - 1:
            valor, sonando = max(cantada, 1.0), max(cantada, 1.0)
        elif pausas[i]:
            sonando = cantada
            resto = iois[i] / pulso - sonando
            valor = sonando + (2.0 if resto >= 2.0 else 1.0)
        else:
            valor = _valor_ritmico(iois[i] / pulso)
            sonando = min(valor, cantada)

        resultado.append(NotaCuantizada(
            nota=n.nota,
            inicioPulsos=round(posicion, 4),
            duracionPulsos=round(sonando, 4),
            velocidad=n.velocidad,
            ajustada=True,
            expresion=n.expresion,
        ))
        posicion += valor
    return resultado


# ----------------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------------

def regularizar_fiel(notas: list[NotaMusical], bpm: float) -> list[NotaCuantizada]:
    """Ajuste absoluto suave, sin sumar el error de redondear cada intervalo.

    Solo comprime silencios reales de respiración, nunca una nota sostenida.
    Compara semicorcheas y tresillos; fuera de la tolerancia conserva el gesto.
    """
    ordenadas = sorted(notas, key=lambda n: n.inicio)
    pulso = 60 / bpm
    posiciones = [0.0]
    for actual, siguiente in pairwise(ordenadas):
        distancia = (siguiente.inicio - actual.inicio) / pulso
        silencio = max(0.0, siguiente.inicio - actual.inicio - actual.duracion) / pulso
        if silencio > max(1.5, .7 / pulso):
            distancia -= silencio - min(2.0, silencio)
        posiciones.append(posiciones[-1] + distancia)
    valores = np.asarray(posiciones)
    error_binario = float(np.mean(np.abs(valores - np.round(valores * 4) / 4)))
    error_ternario = float(np.mean(np.abs(valores - np.round(valores * 3) / 3)))
    division = 3 if error_binario > .025 and error_ternario < .75 * error_binario else 4
    tolerancia = .10
    ajustadas = [round(p * division) / division if abs(p - round(p * division) / division) <= tolerancia
                 else p for p in posiciones]
    # Un ajuste no puede juntar ni invertir ataques de notas rápidas.
    for i in range(1, len(ajustadas)):
        if ajustadas[i] <= ajustadas[i-1]:
            ajustadas[i-1], ajustadas[i] = posiciones[i-1], posiciones[i]
    resultado = []
    for i, (nota, inicio) in enumerate(zip(ordenadas, ajustadas, strict=True)):
        duracion = nota.duracion / pulso
        fin_objetivo = round((inicio + duracion) * division) / division
        if fin_objetivo > inicio and abs(fin_objetivo - inicio - duracion) <= tolerancia:
            duracion = fin_objetivo - inicio
        if i + 1 < len(ajustadas):
            duracion = min(duracion, ajustadas[i+1] - inicio)
        resultado.append(NotaCuantizada(nota=nota.nota, inicioPulsos=round(inicio, 5),
                                        duracionPulsos=round(max(.00001, duracion), 5), velocidad=nota.velocidad,
                                        ajustada=abs(inicio-posiciones[i]) > 1e-6, expresion=nota.expresion))
    return resultado


def analizar(notas: list[NotaMusical], ruta_wav: Path | None, config) -> AnalisisMusical:
    """
    Punto de entrada de la etapa. `ruta_wav` es el audio preprocesado, solo
    para la segunda opinión de librosa (puede ser None en tests).

    Dos caminos, según el tarareo:
    - RITMO MEDIDO: las notas encajan en una grilla mejor que el azar → se usa
      ese tempo y se cuantiza suave (se respeta cómo se cantó).
    - RITMO LIBRE: no hay pulso estable (lo normal al tararear una idea) → el
      sistema pone el pulso: tempo por la nota típica y ritmo reescrito por
      proporciones. Sigue siendo la melodía tarareada, ahora en tiempo.

    Solo se falla si hay tan pocas notas que no hay nada que entender.
    """
    if len(notas) < config.analisis_notas_minimas:
        raise ErrorAudioInvalido(
            MotivoFallo.SIN_MELODIA_CLARA,
            f"Se entendieron solo {len(notas)} notas, no alcanzan para sacar el ritmo y la "
            "tonalidad. Probá tararear una frase más larga, marcando cada nota.",
        )

    onsets = np.array(sorted(n.inicio for n in notas), dtype=np.float64)
    duraciones = np.array([n.duracion for n in sorted(notas, key=lambda x: x.inicio)], dtype=np.float64)

    bpm_librosa = tempo_librosa(ruta_wav) if ruta_wav is not None else None
    bpm_medido, alineacion = estimar_bpm(onsets, config, bpm_librosa)
    azar_promedio, azar_p95 = alineacion_por_azar(len(onsets), float(onsets[-1] - onsets[0]), config)
    # Confianza relativa al azar: 0 = no mejor que notas al azar, 1 = grilla perfecta.
    confianza_bpm = float(np.clip((alineacion - azar_promedio) / (1.0 - azar_promedio), 0.0, 1.0))
    tonalidad, confianza_tonalidad = estimar_tonalidad(notas)

    if alineacion > azar_p95:
        ritmo = RITMO_MEDIDO
        bpm = bpm_medido
        pulso_cero = estimar_pulso_cero(onsets, duraciones, bpm, config.analisis_tolerancia_cuantizacion)
        cuantizada = cuantizar(notas, bpm, pulso_cero, config.analisis_tolerancia_cuantizacion)
        motivo = (f"las notas caen en una grilla de {bpm:.0f} BPM mejor que al azar "
                  f"(alineación {alineacion:.2f} contra {azar_p95:.2f})")
    else:
        ritmo = RITMO_LIBRE
        bpm = tempo_por_densidad(onsets, config)
        pulso_cero = float(onsets[0])
        cuantizada = regularizar_fiel(notas, bpm) if config.analisis_ritmo_fiel else regularizar(notas, bpm)
        pausas = int(detectar_pausas(np.diff(onsets)).sum())
        motivo = (f"tarareo en tiempo libre (alineación {alineacion:.2f}, el azar da hasta "
                  f"{azar_p95:.2f}): tempo {bpm:.0f} por la nota típica, ritmo reescrito por "
                  f"proporciones, {pausas} pausa(s) entre frases convertidas en silencios")

    if ritmo == RITMO_LIBRE and config.analisis_ritmo_fiel:
        motivo = (f"tarareo en tiempo libre: pulso propuesto de {bpm:.0f} BPM; "
                  "ajuste suave sobre posiciones absolutas, admite tresillos y conserva "
                  "la articulación y las notas sostenidas; solo acorta silencios largos")

    logger.info(
        "Análisis: ritmo %s, %.1f BPM (confianza %.2f, librosa %s), %s (correlación %.2f). %s",
        ritmo, bpm, confianza_bpm, f"{bpm_librosa:.1f}" if bpm_librosa else "sin dato",
        tonalidad, confianza_tonalidad, motivo,
    )

    return AnalisisMusical(
        bpm=bpm,
        confianzaBpm=round(confianza_bpm, 3),
        bpmLibrosa=round(bpm_librosa, 1) if bpm_librosa else None,
        ritmo=ritmo,
        motivoRitmo=motivo,
        desfasePulsoSegundos=round(pulso_cero, 4),
        tonalidad=tonalidad,
        confianzaTonalidad=round(confianza_tonalidad, 3),
        compas=COMPAS_POR_DEFECTO,
        melodiaCuantizada=cuantizada,
    )
