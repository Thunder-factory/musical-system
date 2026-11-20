"""
Etapa 6.5 del pipeline: ESTILO INFERIDO.

El usuario no elige género: el estilo con que se produce la canción sale de
CÓMO se tarareó. Se miden seis rasgos (tempo, modo, densidad, articulación,
rango y saltos) y se comparan con el perfil ideal de cada estilo.

Por qué reglas y no un modelo: no se entrena nada, no hay datos de
"tarareo → estilo" y así cada decisión queda explicada en el analisis.json.

Los estilos son una TABLA (`PERFILES`): sumar uno es agregar una fila y su
arreglo en la etapa 7. Solo están los que se distinguen con lo que se mide;
bossa, reggae o vals dependen de síncopa o compás de 3, que no se pueden
medir en un tarareo de ritmo libre. Electrónico se agregó (2026-11-14) al
medir la repetición de motivos.

Además de elegir, informa la CONFIANZA (cuánto le ganó al segundo) y si el
tarareo es ambiguo entre dos estilos, con un mensaje listo para el usuario.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np

from app.modelos import AnalisisMusical, EstiloInferido, NotaMusical, RasgosTarareo
from app.pipeline.analisis import detectar_pausas

logger = logging.getLogger(__name__)

# Si los dos mejores quedan a menos de esto, es un empate práctico y se elige
# el más neutro de los dos (ver ORDEN_NEUTRALIDAD).
MARGEN_EMPATE = 0.03
# Del más neutro (combina con casi todo) al más marcado.
ORDEN_NEUTRALIDAD = ("pop", "folk", "balada", "lofi", "rock_suave", "epico", "electronico")
SEMITONOS_DE_UN_SALTO = 2  # más de un tono ya es salto
PUNTAJE_RASGO_QUE_ENCAJA = 0.75
# Un estilo se ofrece como versión alternativa si su puntaje llega a esto
# (encaja razonablemente con el tarareo). Medido con el lote del 2026-11-14:
# los segundos y terceros estilos van de 0.53 a 0.96; con 0.6 casi todos los
# tarareos tienen 1-2 alternativas y nunca se ofrece algo que no encaja.
UMBRAL_ALTERNATIVA = 0.6
MAXIMO_ALTERNATIVAS = 2
# Repetición: figuras de 4 notas = 3 intervalos seguidos iguales (cualquier
# transposición, cualquier ritmo). Medido 2026-11-14: los 9 tarareos del lote
# dan 0.00-0.22; notas al azar 0.00 (p95 0.00); un motivo repetido 1.00.
INTERVALOS_POR_FIGURA = 3
# Confianza: un margen de 0.25 sobre el segundo estilo ya es confianza total.
# Por debajo de 0.08 de margen el tarareo se considera ambiguo.
MARGEN_CONFIANZA_TOTAL = 0.25
MARGEN_AMBIGUO = 0.08
NOMBRES = {
    "balada": "balada", "pop": "pop", "rock_suave": "rock suave", "lofi": "lo-fi",
    "folk": "folk", "epico": "épico", "electronico": "electrónico",
}


@dataclass(frozen=True)
class Rango:
    """Rango ideal de un rasgo: puntaje 1 adentro, cae lineal a 0 en `margen` afuera."""

    minimo: float
    maximo: float
    margen: float
    peso: float

    def puntaje(self, valor: float) -> float:
        distancia = max(self.minimo - valor, valor - self.maximo, 0.0)
        return max(0.0, 1.0 - distancia / self.margen)


@dataclass(frozen=True)
class Perfil:
    rangos: dict[str, Rango]
    modo: dict[str, float] = field(default_factory=dict)  # puntaje por modo
    peso_modo: float = 0.0


PERFILES: dict[str, Perfil] = {
    "balada": Perfil(rangos={
        "bpm": Rango(55, 85, 15, 2.0),
        "articulacion": Rango(0.80, 1.0, 0.20, 1.5),
        "densidad": Rango(0.0, 1.0, 0.5, 1.0),
        # Una balada no suele recorrer más de una octava y algo; con rango
        # muy amplio y modo menor, el tarareo se acerca más a épico.
        "rango": Rango(0, 14, 4, 0.5),
    }),
    "pop": Perfil(rangos={
        "bpm": Rango(90, 125, 15, 2.0),
        "densidad": Rango(0.8, 1.8, 0.5, 1.0),
        "saltos": Rango(0.2, 0.5, 0.2, 0.5),
        # Un estribillo pop se repite, pero un loop constante ya es electrónico:
        # sin esto, pop y electrónico empatan en un tarareo rápido y repetitivo.
        "repeticion": Rango(0.0, 0.5, 0.2, 0.5),
    }, modo={"mayor": 1.0, "menor": 0.6}, peso_modo=1.0),
    "rock_suave": Perfil(rangos={
        "bpm": Rango(105, 145, 15, 2.0),
        "articulacion": Rango(0.3, 0.75, 0.2, 1.5),
        "saltos": Rango(0.4, 1.0, 0.2, 1.0),
        "rango": Rango(9, 24, 4, 0.5),
    }),
    "lofi": Perfil(rangos={
        "bpm": Rango(65, 95, 10, 2.0),
        "rango": Rango(0, 9, 3, 1.5),
        "densidad": Rango(0.5, 1.3, 0.4, 0.5),
        "articulacion": Rango(0.6, 1.0, 0.2, 0.5),
    }),
    "folk": Perfil(rangos={
        "bpm": Rango(80, 115, 15, 1.5),
        "saltos": Rango(0.0, 0.3, 0.15, 1.5),
        "articulacion": Rango(0.75, 1.0, 0.2, 1.0),
    }, modo={"mayor": 1.0, "menor": 0.5}, peso_modo=1.0),
    "epico": Perfil(rangos={
        "bpm": Rango(55, 100, 15, 1.0),
        "rango": Rango(12, 30, 4, 2.0),
        "densidad": Rango(0.0, 1.0, 0.4, 1.0),
    }, modo={"menor": 1.0, "mayor": 0.3}, peso_modo=1.5),
    "electronico": Perfil(rangos={
        # Lo que lo define es la REPETICIÓN de motivos (un "loop"); sin ella,
        # un tarareo rápido es pop o rock. El umbral 0.5 queda muy por encima
        # de lo que dan los tarareos del lote (≤ 0.22).
        "repeticion": Rango(0.5, 1.0, 0.2, 2.5),
        "bpm": Rango(110, 135, 15, 2.0),
        "densidad": Rango(1.0, 2.5, 0.5, 1.0),
        "articulacion": Rango(0.3, 0.8, 0.2, 0.5),
    }),
}


# ----------------------------------------------------------------------------
# Rasgos
# ----------------------------------------------------------------------------

def medir_articulacion(melodia: list[NotaMusical]) -> float:
    """
    Qué fracción del espacio hasta la nota siguiente se sostuvo cada nota,
    con el timing ORIGINAL del audio (no el regularizado). Las pausas entre
    frases no cuentan: ahí el silencio es respirar, no staccato.
    """
    ordenadas = sorted(melodia, key=lambda n: n.inicio)
    if len(ordenadas) < 2:
        return 1.0
    iois = np.diff([n.inicio for n in ordenadas])
    pausas = detectar_pausas(iois)
    fracciones = [
        min(1.0, n.duracion / ioi)
        for n, ioi, es_pausa in zip(ordenadas, iois, pausas, strict=False)
        if ioi > 0 and not es_pausa
    ]
    return float(np.mean(fracciones)) if fracciones else 1.0


def medir_repeticion(alturas: list[int]) -> float:
    """
    Qué fracción de las figuras de 4 notas de la melodía aparece más de una
    vez. Se comparan INTERVALOS (no notas ni duraciones): la misma figura
    transpuesta o cantada con otro ritmo cuenta como repetición, que es como
    se oye un "loop" en un tarareo libre.
    """
    intervalos = [b - a for a, b in pairwise(alturas)]
    figuras = [tuple(intervalos[i:i + INTERVALOS_POR_FIGURA])
               for i in range(len(intervalos) - INTERVALOS_POR_FIGURA + 1)]
    if not figuras:
        return 0.0
    cuantas = Counter(figuras)
    return sum(1 for f in figuras if cuantas[f] > 1) / len(figuras)


def medir_rasgos(melodia: list[NotaMusical], analisis: AnalisisMusical) -> RasgosTarareo:
    cuantizada = analisis.melodiaCuantizada
    alturas = [n.nota for n in cuantizada]
    intervalos = np.abs(np.diff(alturas)) if len(alturas) > 1 else np.array([])
    pulsos = max(n.inicioPulsos + n.duracionPulsos for n in cuantizada) - min(n.inicioPulsos for n in cuantizada)

    return RasgosTarareo(
        bpm=analisis.bpm,
        modo="menor" if analisis.tonalidad.endswith("minor") else "mayor",
        densidad=round(len(cuantizada) / pulsos, 3) if pulsos > 0 else 0.0,
        articulacion=round(medir_articulacion(melodia), 3),
        rango=int(max(alturas) - min(alturas)),
        saltos=round(float(np.mean(intervalos > SEMITONOS_DE_UN_SALTO)), 3) if intervalos.size else 0.0,
        repeticion=round(medir_repeticion(alturas), 3),
    )


# ----------------------------------------------------------------------------
# Decisión
# ----------------------------------------------------------------------------

def _describir(rasgo: str, r: RasgosTarareo) -> str:
    """Un rasgo en palabras, para el motivo."""
    if rasgo == "bpm":
        ritmo = "lento" if r.bpm < 85 else "movido" if r.bpm >= 110 else "tempo medio"
        return f"{r.bpm:.0f} BPM ({ritmo})"
    if rasgo == "articulacion":
        forma = "ligadas" if r.articulacion >= 0.75 else "algo separadas" if r.articulacion >= 0.55 else "cortadas"
        return f"notas {forma} ({r.articulacion:.2f})"
    if rasgo == "densidad":
        cantidad = "pocas" if r.densidad < 0.9 else "muchas" if r.densidad > 1.6 else "algunas"
        return f"{cantidad} notas por tiempo ({r.densidad:.2f})"
    if rasgo == "rango":
        amplitud = "amplio" if r.rango >= 12 else "corto" if r.rango <= 9 else "medio"
        return f"rango {amplitud} ({r.rango} semitonos)"
    if rasgo == "saltos":
        forma = "con saltos" if r.saltos >= 0.4 else "va por grados" if r.saltos <= 0.3 else "algunos saltos"
        return f"melodía {forma} ({r.saltos:.0%} de saltos)"
    if rasgo == "repeticion":
        return f"motivos que se repiten ({r.repeticion:.0%})"
    return f"modo {r.modo}"


Aporte = tuple[float, str, float]  # (peso × puntaje, rasgo, puntaje del rasgo 0-1)


def puntuar(rasgos: RasgosTarareo) -> dict[str, tuple[float, list[Aporte]]]:
    """Para cada estilo: (puntaje 0-1, aportes de cada rasgo)."""
    valores = rasgos.model_dump()
    resultado = {}
    for nombre, perfil in PERFILES.items():
        aportes: list[Aporte] = []
        for rasgo, r in perfil.rangos.items():
            puntaje = r.puntaje(valores[rasgo])
            aportes.append((r.peso * puntaje, rasgo, puntaje))
        peso_total = sum(r.peso for r in perfil.rangos.values())
        if perfil.peso_modo:
            puntaje_modo = perfil.modo.get(rasgos.modo, 0.0)
            aportes.append((perfil.peso_modo * puntaje_modo, "modo", puntaje_modo))
            peso_total += perfil.peso_modo
        resultado[nombre] = (sum(a for a, _, _ in aportes) / peso_total, aportes)
    return resultado


def elegir_estilo(rasgos: RasgosTarareo) -> EstiloInferido:
    puntajes = puntuar(rasgos)
    ranking = sorted(puntajes, key=lambda nombre: puntajes[nombre][0], reverse=True)
    primero, segundo = ranking[0], ranking[1]

    elegido = primero
    empate = puntajes[primero][0] - puntajes[segundo][0] < MARGEN_EMPATE
    if empate:
        elegido = min((primero, segundo), key=ORDEN_NEUTRALIDAD.index)

    # El motivo nombra solo rasgos que ENCAJAN con el estilo (puntaje ≥ 0.75),
    # los de más peso primero: nunca "balada porque … notas cortadas".
    principales = [
        rasgo for _, rasgo, puntaje in sorted(puntajes[elegido][1], reverse=True)
        if puntaje >= PUNTAJE_RASGO_QUE_ENCAJA
    ][:3]
    motivo = " + ".join(_describir(rasgo, rasgos) for rasgo in principales)
    if empate:
        motivo += f" (empate práctico con {segundo if elegido == primero else primero}: se elige el más neutro)"

    alternativa = segundo if elegido == primero else primero
    alternativas = [nombre for nombre in ranking
                    if nombre != elegido and puntajes[nombre][0] >= UMBRAL_ALTERNATIVA][:MAXIMO_ALTERNATIVAS]
    margen = puntajes[primero][0] - puntajes[segundo][0]
    confianza = float(np.clip(margen / MARGEN_CONFIANZA_TOTAL, 0.0, 1.0))
    ambiguo = margen < MARGEN_AMBIGUO
    if ambiguo:
        mensaje = (f"Tu tarareo suena entre {NOMBRES[elegido]} y {NOMBRES[alternativa]}; "
                   f"la canción va en {NOMBRES[elegido]}.")
    else:
        mensaje = f"Tu tarareo suena a {NOMBRES[elegido]}."

    logger.info("Estilo inferido: %s (confianza %.2f%s) — %s", elegido, confianza,
                f", ambiguo con {alternativa}" if ambiguo else "", motivo)
    return EstiloInferido(
        preset=elegido,
        motivo=motivo,
        puntajes={nombre: round(puntajes[nombre][0], 3) for nombre in ranking},
        rasgos=rasgos,
        confianza=round(confianza, 3),
        alternativa=alternativa,
        alternativas=alternativas,
        ambiguo=ambiguo,
        mensaje=mensaje,
    )


def inferir_estilo(melodia: list[NotaMusical], analisis: AnalisisMusical) -> EstiloInferido:
    """Punto de entrada de la etapa: mide los rasgos y elige el estilo."""
    return elegir_estilo(medir_rasgos(melodia, analisis))
