"""
Etapa 4 del pipeline: LIMPIEZA.

basic-pitch devuelve notas crudas con defectos típicos de tararear (no de
tocar un instrumento): armónicos que se detectan como nota aparte, notas
que se cortan a la mitad, y fragmentos espurios. Las 4 reglas de acá están
MEDIDAS contra un tarareo real (ver CLAUDE.md), no inventadas, y se aplican
siempre en este orden porque cada una asume el resultado de la anterior:

1. Notas partidas — se fusionan primero porque un fundamental fragmentado
   en varios pedazos cortos puede no solaparse en el tiempo con su
   armónico, y entonces la regla de octava (paso 2) no lo detecta: cada
   fragmento por separado es demasiado corto para cubrir la ventana del
   armónico. Fusionar antes junta esos fragmentos en una nota larga que
   sí se solapa, y ahí la regla de octava los detecta correctamente
   (comprobado en tests/audio/mi_tarareo.wav, ~1.9s: un fundamental
   partido en dos con un armónico superpuesto).
2. Duplicación de octava — ya sobre notas fusionadas, para que el
   solapamiento en el tiempo sea el real y no el de un fragmento parcial.
   El desempate NO es por amplitud: se conserva la nota más cercana a la
   mediana de pitches de la melodía completa (calculada sobre el
   resultado de la fusión). La amplitud puede favorecer al armónico si el
   fundamental quedó fragmentado de forma desigual antes de fusionarse
   (se vio en mi_tarareo.wav: con amplitud como criterio, el fundamental
   en 46 perdía contra su armónico en 58); la mediana no tiene ese sesgo
   porque siempre apunta al registro real de la voz, sea que basic-pitch
   detecte el armónico de arriba o un subarmónico de abajo. Solo se usa
   amplitud como desempate final si ambas notas quedan a la misma
   distancia de la mediana.
3. Fuera de rango (±1 octava de la mediana) — mediana recalculada ya sin
   duplicados de octava, para que sea representativa de la melodía real.
4. Señal débil (amplitud/duración) — último filtro, sobre lo que ya está
   limpio de ruido estructural.
"""

from __future__ import annotations

import logging
import statistics

from app.modelos import MotivoDescarte, NotaDescartada, NotaMusical
from app.pipeline.melodia import NotaCruda

logger = logging.getLogger(__name__)


def _se_solapan(a: NotaCruda, b: NotaCruda) -> bool:
    return a.inicio < b.fin and b.inicio < a.fin


def _detectar_octava_duplicada(
    notas: list[NotaCruda], semitonos_octava: int, mediana_referencia: float
) -> tuple[list[NotaCruda], list[tuple[NotaCruda, MotivoDescarte]]]:
    """
    Si dos notas se solapan y difieren exactamente una octava, descarta la
    que esté más lejos de `mediana_referencia` (el pitch central de la
    melodía completa). Es más robusto que comparar amplitud: funciona
    tanto si basic-pitch detecta el armónico de arriba como un
    subarmónico de abajo, porque la mediana siempre apunta al registro
    real de la voz — mientras que la amplitud puede favorecer al
    armónico si el fundamental quedó fragmentado de forma desigual antes
    de fusionarse. Si ambas quedan a la misma distancia (caso simétrico),
    se desempata por amplitud.
    """
    n = len(notas)
    descartar = set()
    for i in range(n):
        if i in descartar:
            continue
        for j in range(i + 1, n):
            if j in descartar:
                continue
            if _se_solapan(notas[i], notas[j]) and abs(notas[i].nota - notas[j].nota) == semitonos_octava:
                distancia_i = abs(notas[i].nota - mediana_referencia)
                distancia_j = abs(notas[j].nota - mediana_referencia)
                if distancia_i != distancia_j:
                    perdedor = i if distancia_i > distancia_j else j
                else:
                    perdedor = i if notas[i].amplitud < notas[j].amplitud else j
                descartar.add(perdedor)
                if perdedor == i:
                    break  # `i` ya no compite, pasar a la siguiente nota base

    supervivientes = [nota for idx, nota in enumerate(notas) if idx not in descartar]
    descartadas = [(notas[idx], MotivoDescarte.OCTAVA_DUPLICADA) for idx in sorted(descartar)]
    return supervivientes, descartadas


def _fusionar_notas_partidas(
    notas: list[NotaCruda], hueco_maximo_segundos: float
) -> tuple[list[NotaCruda], list[tuple[NotaCruda, MotivoDescarte]]]:
    """Fusiona notas consecutivas del mismo pitch separadas por un hueco chico (o que se solapan)."""
    ordenadas = sorted(notas, key=lambda nota: (nota.nota, nota.inicio))
    resultado: list[NotaCruda] = []
    descartadas: list[tuple[NotaCruda, MotivoDescarte]] = []
    actual: NotaCruda | None = None

    for nota in ordenadas:
        if actual is not None and nota.nota == actual.nota and (nota.inicio - actual.fin) < hueco_maximo_segundos:
            dur_actual = actual.fin - actual.inicio
            dur_nueva = nota.fin - nota.inicio
            dur_total = dur_actual + dur_nueva
            amplitud = (
                (actual.amplitud * dur_actual + nota.amplitud * dur_nueva) / dur_total
                if dur_total > 0 else max(actual.amplitud, nota.amplitud)
            )
            descartadas.append((nota, MotivoDescarte.FUSIONADA))
            # max(): si la nota nueva queda contenida dentro de la actual, la
            # fusión no debe acortar la nota (antes tomaba nota.fin a ciegas).
            fin = max(actual.fin, nota.fin)
            actual = NotaCruda(nota=actual.nota, inicio=actual.inicio, fin=fin, amplitud=amplitud)
        else:
            if actual is not None:
                resultado.append(actual)
            actual = nota

    if actual is not None:
        resultado.append(actual)

    return sorted(resultado, key=lambda nota: nota.inicio), descartadas


def _filtrar_fuera_de_rango(
    notas: list[NotaCruda], margen_semitonos: float, confirmadas=None
) -> tuple[list[NotaCruda], list[tuple[NotaCruda, MotivoDescarte]]]:
    """Descarta lo que caiga fuera de ±margen_semitonos de la mediana de pitches."""
    if not notas:
        return notas, []

    mediana = statistics.median(nota.nota for nota in notas)
    supervivientes, descartadas = [], []
    for nota in notas:
        if abs(nota.nota - mediana) > margen_semitonos and (nota.nota, nota.inicio) not in (confirmadas or set()):
            descartadas.append((nota, MotivoDescarte.FUERA_DE_RANGO))
        else:
            supervivientes.append(nota)
    return supervivientes, descartadas


def _filtrar_senal_debil(
    notas: list[NotaCruda], amplitud_minima: float, duracion_minima_segundos: float, confirmadas=None
) -> tuple[list[NotaCruda], list[tuple[NotaCruda, MotivoDescarte]]]:
    """Descarta fragmentos con amplitud o duración por debajo del mínimo."""
    supervivientes, descartadas = [], []
    for nota in notas:
        corroborada = (nota.nota, nota.inicio) in (confirmadas or set()) and nota.amplitud >= .2
        if (nota.amplitud < amplitud_minima and not corroborada) or (nota.fin - nota.inicio) < duracion_minima_segundos:
            descartadas.append((nota, MotivoDescarte.SENAL_DEBIL))
        else:
            supervivientes.append(nota)
    return supervivientes, descartadas


def limpiar_notas(notas_crudas: list[NotaCruda], config, confirmadas=None) -> tuple[list[NotaMusical], list]:
    """
    Aplica las 4 reglas en orden y convierte lo que sobrevive a NotaMusical.

    Devuelve (notas_finales, notas_descartadas) — notas_descartadas usa el
    modelo NotaDescartada de modelos.py, para que main.py lo vuelque tal
    cual en analisis.json.
    """
    notas = notas_crudas
    todas_descartadas: list[tuple[NotaCruda, MotivoDescarte]] = []

    notas, descartadas = _fusionar_notas_partidas(notas, config.limpieza_hueco_fusion_ms / 1000)
    todas_descartadas += descartadas
    if confirmadas:
        confirmadas = {(n.nota, n.inicio) for n in notas
                       if any(pitch == n.nota and n.inicio <= inicio < n.fin for pitch, inicio in confirmadas)}
    logger.info("Tras fusión de partidas: %d notas (-%d)", len(notas), len(descartadas))

    mediana_referencia = statistics.median(nota.nota for nota in notas) if notas else 0.0
    notas, descartadas = _detectar_octava_duplicada(notas, config.limpieza_semitonos_octava, mediana_referencia)
    todas_descartadas += descartadas
    logger.info(
        "Tras octava duplicada: %d notas (-%d), mediana de referencia=%.1f",
        len(notas), len(descartadas), mediana_referencia,
    )

    margen_semitonos = config.limpieza_margen_octavas_mediana * config.limpieza_semitonos_octava
    notas, descartadas = _filtrar_fuera_de_rango(notas, margen_semitonos, confirmadas)
    todas_descartadas += descartadas
    logger.info("Tras filtro de rango: %d notas (-%d)", len(notas), len(descartadas))

    notas, descartadas = _filtrar_senal_debil(
        notas, config.limpieza_amplitud_minima, config.limpieza_duracion_minima_ms / 1000, confirmadas
    )
    todas_descartadas += descartadas
    logger.info("Tras filtro de señal débil: %d notas (-%d)", len(notas), len(descartadas))

    notas_finales = [
        NotaMusical(
            nota=nota.nota,
            inicio=round(nota.inicio, 3),
            duracion=round(nota.fin - nota.inicio, 3),
            velocidad=max(0, min(127, round(nota.amplitud * 127))),
        )
        for nota in sorted(notas, key=lambda nota: nota.inicio)
    ]
    notas_descartadas = [
        NotaDescartada(nota=nota.nota, inicio=round(nota.inicio, 3), motivo=motivo)
        for nota, motivo in todas_descartadas
    ]

    logger.info("Limpieza terminada: %d notas crudas -> %d finales", len(notas_crudas), len(notas_finales))
    return notas_finales, notas_descartadas
