"""
Etapa 6 del pipeline: ARMONÍA.

Elige acordes que acompañen la melodía tarareada: acordes que CONTIENEN las
notas que se cantaron, no una progresión genérica. Reglas explicables, sin
modelos (no se entrena nada):

1. COMPASES: 4/4 desde el pulso 0 de la etapa 5. Si la melodía empieza con
   una nota "de entrada" (anacrusa), se prueban los 4 corrimientos y se elige
   el que deja las notas largas sobre el primer tiempo.
2. CANDIDATOS: las tríadas propias de la tonalidad (en menor, también el V
   mayor, que da el cierre más fuerte).
3. AJUSTE: cada acorde se puntúa por cuántas notas de la melodía contiene,
   pesando más las largas y las que caen en tiempo fuerte. Una nota corta de
   paso casi no cuenta.
4. SECUENCIA: se elige toda la progresión de una vez (programación dinámica,
   tipo Viterbi): suman los movimientos naturales (V→I, IV→V, ii→V...),
   empezar y terminar en la tónica; resta repetir muchos compases seguidos.
5. RITMO ARMÓNICO: un acorde por compás; dos si ninguno cubre bien el
   compás entero (menos del 60 %).

Solo tríadas: enriquecer los acordes (séptimas, etc.) es trabajo del
arreglo (etapa 7), según el estilo inferido.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from app.modelos import AcordeEnTiempo, AnalisisArmonia, NotaCuantizada

logger = logging.getLogger(__name__)

PULSOS_POR_COMPAS = 4
COBERTURA_MINIMA_COMPAS_ENTERO = 0.60

# Peso de la melodía frente a las transiciones en la programación dinámica.
PESO_AJUSTE = 2.0
BONUS_EMPIEZA_EN_TONICA = 0.5
BONUS_TERMINA_EN_TONICA = 0.8
PENALIZACION_REPETIR = (0.0, 0.3, 0.8)  # 1.ª vez, 2.ª seguida, 3.ª o más seguidas

# Cuánto suma/resta una nota de la melodía según su relación con el acorde.
SUMA_NOTA_DEL_ACORDE = 1.0
EXTRA_FUNDAMENTAL = 0.2
RESTA_NOTA_DE_LA_ESCALA = -0.5
RESTA_NOTA_CROMATICA = -1.0

_NOMBRES_SOSTENIDOS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_NOMBRES_BEMOLES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
_LETRAS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

ESCALA_MAYOR = (0, 2, 4, 5, 7, 9, 11)
ESCALA_MENOR = (0, 2, 3, 5, 7, 8, 10)
TERCERA = {"mayor": 4, "menor": 3}


@dataclass(frozen=True)
class AcordeCandidato:
    grado: str
    intervalo: int  # semitonos desde la tónica hasta la fundamental
    calidad: str  # "mayor" | "menor"
    tonica: bool  # cumple función de tónica (para empezar/terminar)


ACORDES_MAYOR = (
    AcordeCandidato("I", 0, "mayor", True),
    AcordeCandidato("ii", 2, "menor", False),
    AcordeCandidato("iii", 4, "menor", False),
    AcordeCandidato("IV", 5, "mayor", False),
    AcordeCandidato("V", 7, "mayor", False),
    AcordeCandidato("vi", 9, "menor", False),
)
ACORDES_MENOR = (
    AcordeCandidato("i", 0, "menor", True),
    AcordeCandidato("III", 3, "mayor", False),
    AcordeCandidato("iv", 5, "menor", False),
    AcordeCandidato("v", 7, "menor", False),
    AcordeCandidato("V", 7, "mayor", False),
    AcordeCandidato("VI", 8, "mayor", False),
    AcordeCandidato("VII", 10, "mayor", False),
)

# Movimientos que suenan naturales en la armonía funcional (bonus).
TRANSICIONES_MAYOR = {
    ("V", "I"): 0.6, ("ii", "V"): 0.5, ("IV", "V"): 0.4, ("IV", "I"): 0.3,
    ("I", "IV"): 0.3, ("I", "V"): 0.2, ("I", "vi"): 0.2, ("vi", "IV"): 0.3,
    ("vi", "ii"): 0.3, ("iii", "vi"): 0.3, ("V", "vi"): 0.3, ("I", "ii"): 0.1,
}
TRANSICIONES_MENOR = {
    ("V", "i"): 0.6, ("v", "i"): 0.3, ("iv", "V"): 0.4, ("iv", "i"): 0.3,
    ("i", "iv"): 0.3, ("i", "VI"): 0.2, ("VI", "VII"): 0.3, ("VII", "i"): 0.3,
    ("VII", "III"): 0.3, ("III", "VI"): 0.3, ("VI", "V"): 0.3, ("i", "VII"): 0.2,
}


# ----------------------------------------------------------------------------
# Tonalidad y nombres
# ----------------------------------------------------------------------------

def leer_tonalidad(tonalidad: str) -> tuple[int, str]:
    """ "Bb minor" → (10, "menor"). Acepta lo que produce la etapa 5."""
    tonica, modo = tonalidad.split()
    clase = _LETRAS[tonica[0]] + tonica[1:].count("#") - tonica[1:].count("b")
    return clase % 12, ("menor" if modo == "minor" else "mayor")


def _usa_bemoles(tonica: int, modo: str, nombre_tonica: str) -> bool:
    """Si la armadura de la tonalidad lleva bemoles (para escribir Bb y no A#)."""
    if "b" in nombre_tonica[1:]:
        return True
    relativa_mayor = (tonica + 3) % 12 if modo == "menor" else tonica
    return relativa_mayor in (5, 10, 3, 8, 1)  # F, Bb, Eb, Ab, Db


def nombre_acorde(fundamental: int, calidad: str, bemoles: bool) -> str:
    nombres = _NOMBRES_BEMOLES if bemoles else _NOMBRES_SOSTENIDOS
    return nombres[fundamental % 12] + ("m" if calidad == "menor" else "")


def notas_triada(fundamental: int, calidad: str) -> list[int]:
    """Tríada en posición fundamental, en la octava de Do3 (MIDI 48-59)."""
    raiz = 48 + fundamental % 12
    return [raiz, raiz + TERCERA[calidad], raiz + 7]


# ----------------------------------------------------------------------------
# Compases y ajuste de la melodía
# ----------------------------------------------------------------------------

def peso_metrico(posicion_en_compas: float) -> float:
    """Tiempo 1 pesa más que el 3, que pesa más que 2 y 4; lo que cae entre tiempos, menos."""
    if math.isclose(posicion_en_compas, 0.0, abs_tol=1e-6):
        return 1.0
    if math.isclose(posicion_en_compas, 2.0, abs_tol=1e-6):
        return 0.8
    if math.isclose(posicion_en_compas, round(posicion_en_compas), abs_tol=1e-6):
        return 0.6
    return 0.4


def elegir_anacrusa(notas: list[NotaCuantizada]) -> float:
    """
    Cuántos pulsos de "entrada" hay antes del primer tiempo fuerte (0-3).

    Para cada corrimiento posible se suma la duración de las notas que caen en
    el tiempo 1 (y, con menos peso, en el 3). Las notas largas suelen caer en
    tiempo fuerte. En empate gana 0: no se inventa una anacrusa sin evidencia.
    """
    def puntaje(corrimiento: int) -> float:
        total = 0.0
        for n in notas:
            posicion = (n.inicioPulsos + corrimiento) % PULSOS_POR_COMPAS
            if math.isclose(posicion, 0.0, abs_tol=1e-6):
                total += n.duracionPulsos
            elif math.isclose(posicion, 2.0, abs_tol=1e-6):
                total += 0.5 * n.duracionPulsos
        return total

    return float(max(range(PULSOS_POR_COMPAS), key=lambda c: (puntaje(c), -c)))


def _aportes(notas: list[NotaCuantizada], inicio: float, fin: float, anacrusa: float) -> list[tuple[int, float]]:
    """(clase de altura, peso) de cada nota que suena en [inicio, fin)."""
    aportes = []
    for n in notas:
        solapamiento = min(fin, n.inicioPulsos + n.duracionPulsos) - max(inicio, n.inicioPulsos)
        if solapamiento <= 1e-6:
            continue
        posicion = (max(inicio, n.inicioPulsos) + anacrusa) % PULSOS_POR_COMPAS
        aportes.append((n.nota % 12, solapamiento * peso_metrico(posicion)))
    return aportes


def ajuste(aportes: list[tuple[int, float]], fundamental: int, calidad: str, escala: set[int]) -> tuple[float, float]:
    """
    (puntaje normalizado, cobertura) de un acorde para un tramo de melodía.

    puntaje: promedio ponderado de +1 (nota del acorde, +0.2 si es la
    fundamental), -0.5 (nota de la escala que no está en el acorde) o -1
    (nota cromática). cobertura: fracción del peso que el acorde contiene.
    """
    total = sum(p for _, p in aportes)
    if total <= 0:
        return 0.0, 0.0
    del_acorde = {fundamental % 12, (fundamental + TERCERA[calidad]) % 12, (fundamental + 7) % 12}
    puntos = cubierto = 0.0
    for clase, peso in aportes:
        if clase in del_acorde:
            puntos += peso * (SUMA_NOTA_DEL_ACORDE + (EXTRA_FUNDAMENTAL if clase == fundamental % 12 else 0.0))
            cubierto += peso
        elif clase in escala:
            puntos += peso * RESTA_NOTA_DE_LA_ESCALA
        else:
            puntos += peso * RESTA_NOTA_CROMATICA
    return puntos / total, cubierto / total


# ----------------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------------

def armonizar(notas: list[NotaCuantizada], tonalidad: str) -> AnalisisArmonia:
    tonica, modo = leer_tonalidad(tonalidad)
    bemoles = _usa_bemoles(tonica, modo, tonalidad.split()[0])
    candidatos = ACORDES_MENOR if modo == "menor" else ACORDES_MAYOR
    transiciones = TRANSICIONES_MENOR if modo == "menor" else TRANSICIONES_MAYOR
    escala = {(tonica + i) % 12 for i in (ESCALA_MENOR if modo == "menor" else ESCALA_MAYOR)}
    if modo == "menor":
        escala.add((tonica + 11) % 12)  # la sensible del V mayor no es "cromática" en menor

    anacrusa = elegir_anacrusa(notas)
    fin_melodia = max(n.inicioPulsos + n.duracionPulsos for n in notas)
    cantidad_compases = max(1, math.ceil((fin_melodia + anacrusa) / PULSOS_POR_COMPAS - 1e-6))

    def fundamental_de(c: AcordeCandidato) -> int:
        return (tonica + c.intervalo) % 12

    # Tramos: un compás entero, o dos mitades si ningún acorde cubre bien el compás.
    tramos: list[tuple[int, float, float]] = []  # (compás, inicio, fin) en pulsos de la melodía
    for compas in range(cantidad_compases):
        inicio = compas * PULSOS_POR_COMPAS - anacrusa
        fin = inicio + PULSOS_POR_COMPAS
        aportes = _aportes(notas, inicio, fin, anacrusa)
        mejor_cobertura = max(
            (ajuste(aportes, fundamental_de(c), c.calidad, escala)[1] for c in candidatos), default=0.0
        )
        mitad = inicio + PULSOS_POR_COMPAS / 2
        hay_notas_en_ambas = _aportes(notas, inicio, mitad, anacrusa) and _aportes(notas, mitad, fin, anacrusa)
        if aportes and mejor_cobertura < COBERTURA_MINIMA_COMPAS_ENTERO and hay_notas_en_ambas:
            tramos += [(compas, inicio, mitad), (compas, mitad, fin)]
        else:
            tramos.append((compas, inicio, fin))

    # Matriz de ajuste [tramo][acorde].
    ajustes = [
        [ajuste(_aportes(notas, ini, fin, anacrusa), fundamental_de(c), c.calidad, escala) for c in candidatos]
        for _, ini, fin in tramos
    ]

    # Programación dinámica. Estado: (acorde, cuántas veces seguidas lleva, tope 3).
    cantidad = len(candidatos)
    menos_infinito = float("-inf")
    puntajes = [[[menos_infinito] * 3 for _ in range(cantidad)] for _ in tramos]
    previo: list[list[list[tuple[int, int] | None]]] = [[[None] * 3 for _ in range(cantidad)] for _ in tramos]

    for a, c in enumerate(candidatos):
        puntajes[0][a][0] = PESO_AJUSTE * ajustes[0][a][0] + (BONUS_EMPIEZA_EN_TONICA if c.tonica else 0.0)

    for t in range(1, len(tramos)):
        for b, cb in enumerate(candidatos):
            base = PESO_AJUSTE * ajustes[t][b][0]
            for a, ca in enumerate(candidatos):
                for racha in range(3):
                    anterior = puntajes[t - 1][a][racha]
                    if anterior == menos_infinito:
                        continue
                    if a == b:
                        nueva_racha = min(racha + 1, 2)
                        valor = anterior + base - PENALIZACION_REPETIR[nueva_racha]
                    else:
                        nueva_racha = 0
                        valor = anterior + base + transiciones.get((ca.grado, cb.grado), 0.0)
                    if valor > puntajes[t][b][nueva_racha]:
                        puntajes[t][b][nueva_racha] = valor
                        previo[t][b][nueva_racha] = (a, racha)

    ultimo = len(tramos) - 1
    estado = max(
        ((a, r) for a in range(cantidad) for r in range(3) if puntajes[ultimo][a][r] > menos_infinito),
        key=lambda s: puntajes[ultimo][s[0]][s[1]] + (BONUS_TERMINA_EN_TONICA if candidatos[s[0]].tonica else 0.0),
    )
    elegidos = [0] * len(tramos)
    for t in range(ultimo, -1, -1):
        elegidos[t] = estado[0]
        if t > 0:
            estado = previo[t][estado[0]][estado[1]]

    # Armar la progresión; dos mitades del mismo compás con el mismo acorde se unen.
    progresion: list[AcordeEnTiempo] = []
    for (compas, ini, fin), indice, (_, cobertura) in zip(
        tramos, elegidos, (ajustes[t][elegidos[t]] for t in range(len(tramos))), strict=True
    ):
        c = candidatos[indice]
        inicio = max(0.0, ini)
        if progresion and progresion[-1].compas == compas and progresion[-1].grado == c.grado:
            anterior = progresion[-1]
            progresion[-1] = anterior.model_copy(update={
                "duracionPulsos": fin - anterior.inicioPulsos,
                "cobertura": round((anterior.cobertura + cobertura) / 2, 3),
            })
            continue
        progresion.append(AcordeEnTiempo(
            compas=compas,
            inicioPulsos=round(inicio, 4),
            duracionPulsos=round(fin - inicio, 4),
            nombre=nombre_acorde(fundamental_de(c), c.calidad, bemoles),
            grado=c.grado,
            notas=notas_triada(fundamental_de(c), c.calidad),
            cobertura=round(cobertura, 3),
        ))

    acordes = [a.nombre for a in progresion]
    logger.info(
        "Armonía en %s: %s (anacrusa %g pulsos, %d compases)",
        tonalidad, " | ".join(f"{a.nombre}({a.grado})" for a in progresion), anacrusa, cantidad_compases,
    )
    return AnalisisArmonia(anacrusaPulsos=anacrusa, acordes=acordes, progresion=progresion)
