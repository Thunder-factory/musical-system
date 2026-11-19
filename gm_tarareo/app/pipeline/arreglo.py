"""
Etapa 7 del pipeline: ARREGLO.

Convierte el tarareo (melodía + acordes + estilo) en una canción completa de
60-90 s, en MIDI multipista. Primero se planifica la estructura y después se
llenan las secciones (idea tomada de YuE2: planificar antes de generar):

    intro → A → A' → B → A final → outro

- A es el tarareo tal cual (melodía en el instrumento principal + acordes).
- A' es la misma melodía con el arreglo más lleno y la melodía doblada a la
  octava por una segunda voz.
- B es el contraste: una de 3 progresiones (elegida por la huella del
  tarareo) y el instrumento principal toca el PRIMER MOTIVO del tarareo
  adaptado a esos acordes. Todo sale de la idea tarareada.
- A final suma una segunda voz a distancia de tercera.
- La intro anticipa el primer motivo como "gancho"; el outro frena
  (ritardando) y sostiene el acorde final.
- Se agregan o quitan secciones para quedar entre 60 y 90 s.

Cada estilo (etapa 6.5) define patrones de acompañamiento (uno liviano y uno
lleno), bajo, batería con redobles de transición, y 3 VARIANTES de
instrumentación. La variante sale de los rasgos del tarareo y, si no deciden,
de una huella de la melodía: el mismo tarareo da siempre la misma canción.

Mejoras del 2026-11-14 (pedidas tras escuchar la primera versión): enlace de
voces entre acordes, redobles y platillos en las transiciones, bajo con notas
de paso, 3 progresiones para B, patrones distintos por sección, segunda voz,
gancho en la intro, crescendo y ritardando con acorde final sostenido.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import numpy as np

from app.modelos import (
    AnalisisArmonia,
    AnalisisMusical,
    ArregloCancion,
    ClimaMusical,
    EstiloInferido,
    PistaArreglo,
    RasgosTarareo,
    SeccionArreglo,
)
from app.pipeline.armonia import (
    ACORDES_MAYOR,
    ACORDES_MENOR,
    ESCALA_MAYOR,
    ESCALA_MENOR,
    TERCERA,
    leer_tonalidad,
)
from app.pipeline.gancho import detectar_gancho
from app.pipeline.instrumentacion import ampliar_instrumentacion
from app.pipeline.patrones import adaptar_acompanamiento, variar_patrones

logger = logging.getLogger(__name__)

PULSOS_POR_COMPAS = 4
DURACION_MINIMA_SEGUNDOS = 60.0
DURACION_MAXIMA_SEGUNDOS = 90.0
MAXIMO_SECCIONES_EXTRA = 10

# GM: notas de percusión del canal 10.
BOMBO, BAQUETA, CAJA, HIHAT, HIHAT_ABIERTO, PLATILLO, RIDE, PANDERETA, TOM_GRAVE, MARACAS, PALMAS = (
    36, 37, 38, 42, 46, 49, 51, 54, 45, 70, 39,
)

ENERGIA = {"intro": 0.4, "A": 0.65, "A'": 0.85, "B": 0.7, "A final": 1.0, "outro": 0.5}
ENERGIA_PATRON_LLENO = 0.8  # desde acá el acompañamiento usa su patrón lleno
SECCIONES_A = ("A", "A'", "A final")

# Dinámica y final.
COMPASES_CRESCENDO = 2  # compases de subida antes de A' y A final
SUBIDA_CRESCENDO = 0.25  # hasta +25 % de intensidad
RITARDANDO = 0.25  # el tempo del outro baja hasta un 25 % hacia el final
FERMATA_PULSOS = 2.0  # cuánto se sostiene de más el acorde final
# El ritardando y la fermata alargan el outro ~3/4 de compás: se tiene en cuenta
# al planificar la duración.
COMPASES_EXTRA_OUTRO = 0.75


# ----------------------------------------------------------------------------
# Tablas de estilos y variantes
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Variante:
    nombre: str
    melodia: int  # programa GM del instrumento principal
    acompanamiento: int
    bajo: int
    colchon: int | None = None
    condicion: Callable[[RasgosTarareo], bool] | None = None


@dataclass(frozen=True)
class EstiloArreglo:
    variantes: tuple[Variante, ...]
    acompanamiento: str  # patrón liviano (intro, A, B)
    acompanamiento_lleno: str  # patrón lleno (A', A final)
    bajo: tuple[tuple[float, float, int], ...]  # (posición, duración, intervalo) por compás
    segunda_voz: int  # programa GM de la segunda voz (gancho, octava, tercera)
    bateria: dict[int, tuple[float, ...]] = field(default_factory=dict)  # nota → posiciones
    redoble: dict[int, tuple[float, ...]] = field(default_factory=dict)  # tiempos 3-4 del último compás
    energia_bateria: float = 0.6  # desde qué energía de sección suena la batería
    septimas: bool = False
    swing: bool = False
    colchon_siempre: bool = False
    bajo_con_paso: bool = False  # nota de aproximación antes de cada cambio de acorde


CORCHEAS = tuple(i * 0.5 for i in range(8))
NEGRAS = (0.0, 1.0, 2.0, 3.0)
CONTRATIEMPOS = (0.5, 1.5, 2.5, 3.5)
REDOBLE_CAJA = {BOMBO: (2.0,), CAJA: (2.0, 2.5, 3.0, 3.25, 3.5, 3.75)}

ESTILOS: dict[str, EstiloArreglo] = {
    "balada": EstiloArreglo(
        variantes=(
            Variante("piano", melodia=0, acompanamiento=0, bajo=32, colchon=48),
            Variante("guitarra", melodia=73, acompanamiento=24, bajo=32, colchon=48),
            Variante("cuerdas", melodia=49, acompanamiento=0, bajo=32, colchon=89,
                      condicion=lambda r: r.articulacion >= 0.85),
        ),
        acompanamiento="arpegio_lento", acompanamiento_lleno="arpegio",
        bajo=((0.0, 4.0, 0),),
        segunda_voz=48,
        bateria={BOMBO: (0.0, 2.5), BAQUETA: (1.0, 3.0), HIHAT: NEGRAS},
        redoble={BAQUETA: (2.0, 3.0, 3.5)},
        energia_bateria=0.8, septimas=True,
    ),
    "pop": EstiloArreglo(
        variantes=(
            Variante("piano", melodia=53, acompanamiento=0, bajo=33, colchon=89),
            Variante("guitarra", melodia=80, acompanamiento=25, bajo=33, colchon=89),
            Variante("electrico", melodia=81, acompanamiento=4, bajo=33, colchon=89),
        ),
        acompanamiento="bloques", acompanamiento_lleno="bloques_negras",
        bajo=tuple((p, 0.45, 0) for p in CORCHEAS),
        segunda_voz=52,
        bateria={BOMBO: (0.0, 2.0), CAJA: (1.0, 3.0), HIHAT: CORCHEAS},
        redoble=REDOBLE_CAJA, bajo_con_paso=True,
    ),
    "rock_suave": EstiloArreglo(
        variantes=(
            Variante("distorsion", melodia=29, acompanamiento=30, bajo=34,
                      condicion=lambda r: r.saltos >= 0.5),
            Variante("limpia", melodia=27, acompanamiento=29, bajo=34),
            Variante("organo", melodia=16, acompanamiento=29, bajo=34),
        ),
        acompanamiento="quintas_negras", acompanamiento_lleno="quintas",
        bajo=tuple((p, 0.45, 0) for p in CORCHEAS),
        segunda_voz=27,
        bateria={BOMBO: (0.0, 1.5, 2.0), CAJA: (1.0, 3.0), HIHAT: CORCHEAS},
        redoble={BOMBO: (2.0,), CAJA: (2.0, 2.5, 3.0, 3.25), TOM_GRAVE: (3.5, 3.75)},
        bajo_con_paso=True,
    ),
    "lofi": EstiloArreglo(
        variantes=(
            Variante("rhodes", melodia=11, acompanamiento=4, bajo=33),
            Variante("jazz", melodia=26, acompanamiento=4, bajo=32),
            Variante("flauta", melodia=73, acompanamiento=0, bajo=33),
        ),
        acompanamiento="sincopado", acompanamiento_lleno="sincopado_lleno",
        bajo=((0.0, 1.4, 0), (2.5, 0.9, 0), (3.5, 0.45, 0)),
        segunda_voz=11,
        bateria={BOMBO: (0.0, 1.75, 2.5), CAJA: (1.0, 3.0), HIHAT: CORCHEAS},
        redoble={CAJA: (3.0, 3.5, 3.75)},
        energia_bateria=0.6, septimas=True, swing=True, bajo_con_paso=True,
    ),
    "folk": EstiloArreglo(
        variantes=(
            Variante("violin", melodia=40, acompanamiento=25, bajo=32),
            Variante("nylon", melodia=24, acompanamiento=25, bajo=32,
                      condicion=lambda r: r.modo == "menor"),
            Variante("armonica", melodia=22, acompanamiento=25, bajo=32),
        ),
        acompanamiento="rasgueo_simple", acompanamiento_lleno="rasgueo",
        bajo=((0.0, 1.8, 0), (2.0, 1.8, 7)),
        segunda_voz=73,
        bateria={PANDERETA: (1.0, 3.0), MARACAS: CORCHEAS},
        redoble={PANDERETA: (2.0, 2.5, 3.0, 3.5, 3.75)},
    ),
    "epico": EstiloArreglo(
        variantes=(
            Variante("trompa", melodia=60, acompanamiento=48, bajo=43, colchon=52),
            Variante("coro", melodia=52, acompanamiento=48, bajo=43, colchon=61),
            Variante("metales", melodia=61, acompanamiento=48, bajo=43, colchon=52),
        ),
        acompanamiento="ostinato", acompanamiento_lleno="ostinato_lleno",
        bajo=((0.0, 2.0, 0), (2.0, 2.0, 0)),
        segunda_voz=48,
        bateria={BOMBO: (0.0, 2.0), TOM_GRAVE: (3.0, 3.5)},
        redoble={TOM_GRAVE: (2.0, 2.5, 3.0, 3.25, 3.5, 3.75)},
        energia_bateria=0.7, colchon_siempre=True,
    ),
    "electronico": EstiloArreglo(
        # Bombo en cada tiempo ("four on the floor"), palmas en 2 y 4, hi-hat
        # abierto a contratiempo, bajo de sintetizador a contratiempo y
        # acordes cortos de sintetizador: el loop que pide un tarareo repetitivo.
        variantes=(
            Variante("sierra", melodia=81, acompanamiento=90, bajo=38, colchon=89),
            Variante("cuadrada", melodia=80, acompanamiento=90, bajo=39, colchon=89),
            Variante("cristal", melodia=84, acompanamiento=90, bajo=38, colchon=95),
        ),
        acompanamiento="contratiempo", acompanamiento_lleno="corcheas_acorde",
        bajo=tuple((p, 0.4, 0) for p in CONTRATIEMPOS),
        segunda_voz=88,
        bateria={BOMBO: NEGRAS, PALMAS: (1.0, 3.0), HIHAT_ABIERTO: CONTRATIEMPOS},
        redoble=REDOBLE_CAJA,
    ),
}

# Registro cómodo (nota central) de cada instrumento principal.
CENTRO_REGISTRO = {24: 64, 25: 64, 26: 64, 27: 64, 29: 64, 16: 67, 52: 67, 53: 67, 43: 40}
CENTRO_POR_DEFECTO = 72
NOTA_MAS_AGUDA_SEGUNDA_VOZ = 96

# Progresiones para B (terminan en V para volver a A), elegidas por la huella.
PROGRESIONES_B = {
    "mayor": (("IV", "V", "vi", "V"), ("vi", "IV", "ii", "V"), ("ii", "V", "IV", "V")),
    "menor": (("VI", "VII", "iv", "V"), ("iv", "VI", "III", "V"), ("VI", "iv", "VII", "V")),
}
CIERRE = {"mayor": ("V", "I"), "menor": ("V", "i")}


# ----------------------------------------------------------------------------
# Estructuras internas
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Acorde:
    inicio: float  # pulsos absolutos de la canción
    fin: float
    fundamental: int  # clase de altura 0-11
    calidad: str  # "mayor" | "menor"
    grado: str


@dataclass(frozen=True)
class Evento:
    """Una nota de la canción. `pista` es el rol ("melodia", "bajo"...)."""

    pista: str
    nota: int
    inicio: float  # pulsos
    duracion: float
    velocidad: int
    expresion: tuple[tuple[float, float], ...] = ()
    origenPulsos: float | None = None


@dataclass(frozen=True)
class ResultadoArreglo:
    arreglo: ArregloCancion
    eventos: list[Evento]


@dataclass
class _Tarareo:
    """La sección A, ya acomodada para repetirse: cuerpo en compases enteros + anacrusa."""

    compases: int
    cuerpo: list[tuple[int, float, float, int]]  # (nota, inicio, duración, velocidad) desde el compás 0
    entrada: list[tuple[int, float, float, int]]  # notas de anacrusa, con inicio negativo
    acordes: list[tuple[float, float, int, str, str]]  # (inicio, fin, fundamental, calidad, grado)
    origenes: dict[tuple[float, int], float] = field(default_factory=dict)

    def motivo(self) -> list[tuple[int, float, float, int]]:
        """El primer motivo: las notas del primer compás (o las 3 primeras)."""
        return [x for x in self.cuerpo if x[1] < PULSOS_POR_COMPAS] or self.cuerpo[:3]


# ----------------------------------------------------------------------------
# Preparación del tarareo
# ----------------------------------------------------------------------------

def _calidad(notas_triada: list[int]) -> str:
    return "mayor" if notas_triada[1] - notas_triada[0] == TERCERA["mayor"] else "menor"


def preparar_tarareo(analisis: AnalisisMusical, armonia: AnalisisArmonia) -> _Tarareo:
    """
    Pasa la melodía y los acordes a una línea de tiempo en compases.

    Si hay anacrusa, el compás 0 de la etapa 6 solo tiene la nota de entrada:
    esas notas pasan a `entrada` (suenan al final de la sección anterior) y el
    cuerpo empieza en el primer tiempo fuerte.
    """
    anacrusa = armonia.anacrusaPulsos
    corrimiento = anacrusa - (PULSOS_POR_COMPAS if anacrusa > 0 else 0)

    cuerpo, entrada = [], []
    for n in analisis.melodiaCuantizada:
        posicion = n.inicioPulsos + corrimiento
        destino = entrada if posicion < 0 else cuerpo
        destino.append((n.nota, posicion, n.duracionPulsos, n.velocidad))

    acordes = []
    for a in armonia.progresion:
        compas = a.compas - (1 if anacrusa > 0 else 0)
        if compas < 0:
            continue  # el acorde del compás de anacrusa solo cubre la nota de entrada
        inicio = max(a.inicioPulsos + corrimiento, compas * PULSOS_POR_COMPAS)
        fin = a.inicioPulsos + a.duracionPulsos + corrimiento
        acordes.append((inicio, fin, a.notas[0] % 12, _calidad(a.notas), a.grado))

    if not acordes:  # melodía de un solo compás con anacrusa: se usa el único acorde
        a = armonia.progresion[0]
        acordes = [(0.0, float(PULSOS_POR_COMPAS), a.notas[0] % 12, _calidad(a.notas), a.grado)]

    fin_musica = max([f for _, f, *_ in acordes] + [i + d for _, i, d, _ in cuerpo] + [PULSOS_POR_COMPAS])
    compases = max(1, math.ceil(fin_musica / PULSOS_POR_COMPAS - 1e-6))
    # El último acorde se estira hasta el final del último compás.
    ultimo = acordes[-1]
    acordes[-1] = (ultimo[0], compases * PULSOS_POR_COMPAS, *ultimo[2:])
    origenes = {(n.inicioPulsos + corrimiento, n.nota): n.inicioPulsos for n in analisis.melodiaCuantizada}
    return _Tarareo(compases=compases, cuerpo=cuerpo, entrada=entrada, acordes=acordes, origenes=origenes)


def _tarareo_estribillo(tarareo, gancho, anacrusa, compases):
    """Repite frase Y sus acordes, sin inventar notas ni ponerlas sobre otra armonía."""
    corrimiento = anacrusa - (4 if anacrusa else 0)
    inicio = max(0, gancho.inicioPulsos + corrimiento)
    periodo = gancho.duracionPulsos
    fin_seccion = compases * 4
    cuerpo, acordes, origenes = [], [], {}
    for vuelta in range(math.ceil(fin_seccion / periodo)):
        base = vuelta * periodo
        for nota, t, d, v in tarareo.cuerpo:
            if inicio <= t < inicio + periodo and base + t - inicio < fin_seccion:
                posicion = base + t - inicio
                cuerpo.append((nota, posicion, min(d, periodo - (t-inicio), fin_seccion-posicion), v))
                origenes[(posicion, nota)] = tarareo.origenes.get((t, nota), t-corrimiento)
        for a, b, fund, cal, grado in tarareo.acordes:
            desde, hasta = max(a, inicio), min(b, inicio + periodo)
            if hasta > desde and base + desde - inicio < fin_seccion:
                acordes.append((base + desde-inicio, min(base+hasta-inicio, fin_seccion), fund, cal, grado))
    if not cuerpo or not acordes:
        return tarareo
    return _Tarareo(compases, cuerpo, [], acordes, origenes)


# ----------------------------------------------------------------------------
# Estructura
# ----------------------------------------------------------------------------

def planificar_estructura(compases_a: int, bpm: float) -> list[tuple[str, int]]:
    """
    Lista de (sección, compases) que deja la canción entre 60 y 90 s.

    Se parte de intro-A-A'-B-A final-outro. Si se pasa de 90 s se quita A' y
    después B; si no llega a 60 s se agregan A' y B (alternados) antes del final
    hasta llegar, sin pasarse de 90 s. El tope de 10 es solo de seguridad. El
    outro cuenta con su alargue por el ritardando y la fermata.
    """
    segundos_por_compas = PULSOS_POR_COMPAS * 60.0 / bpm
    compases_b = 4
    secciones = [("intro", 2), ("A", compases_a), ("A'", compases_a), ("B", compases_b),
                 ("A final", compases_a), ("outro", 2)]

    def duracion(s: list[tuple[str, int]]) -> float:
        return (sum(c for _, c in s) + COMPASES_EXTRA_OUTRO) * segundos_por_compas

    for quitar in ("A'", "B"):
        if duracion(secciones) > DURACION_MAXIMA_SEGUNDOS:
            secciones = [s for s in secciones if s[0] != quitar]

    for agregado in range(MAXIMO_SECCIONES_EXTRA):
        if duracion(secciones) >= DURACION_MINIMA_SEGUNDOS:
            break
        extra = ("A'", compases_a) if agregado % 2 == 0 else ("B", compases_b)
        if duracion(secciones + [extra]) > DURACION_MAXIMA_SEGUNDOS:
            break
        secciones.insert(len(secciones) - 2, extra)
    return secciones


# ----------------------------------------------------------------------------
# Elección de variante y de progresión de B
# ----------------------------------------------------------------------------

def huella_melodia(analisis: AnalisisMusical) -> int:
    """Número estable que identifica la melodía (mismo tarareo → mismo número)."""
    texto = ";".join(f"{n.nota},{n.inicioPulsos},{n.duracionPulsos}" for n in analisis.melodiaCuantizada)
    return int(hashlib.sha1(texto.encode()).hexdigest()[:8], 16)


def elegir_variante(preset: str, rasgos: RasgosTarareo, huella: int, forzada: str | None = None) -> Variante:
    variantes = ESTILOS[preset].variantes
    if forzada:
        return next(v for v in variantes if v.nombre == forzada)
    candidatas = [v for v in variantes if v.condicion and v.condicion(rasgos)] or list(variantes)
    return candidatas[huella % len(candidatas)]


def elegir_progresion_b(modo: str, huella: int) -> tuple[str, ...]:
    """Una de las 3 progresiones de B. Se divide la huella por 7 para no repetir la elección de variante."""
    opciones = PROGRESIONES_B[modo]
    return opciones[(huella // 7) % len(opciones)]


# ----------------------------------------------------------------------------
# Acordes de cada sección
# ----------------------------------------------------------------------------

def _acorde_por_grado(grado: str, tonica: int, modo: str) -> tuple[int, str]:
    candidatos = ACORDES_MENOR if modo == "menor" else ACORDES_MAYOR
    c = next(x for x in candidatos if x.grado == grado)
    return (tonica + c.intervalo) % 12, c.calidad


def acordes_de_seccion(nombre: str, inicio: float, compases: int, tarareo: _Tarareo,
                       tonica: int, modo: str, progresion_b: tuple[str, ...]) -> list[Acorde]:
    if nombre in SECCIONES_A:
        return [Acorde(inicio + i, inicio + f, fund, cal, grado) for i, f, fund, cal, grado in tarareo.acordes]
    if nombre == "intro":
        primeros = [a for a in tarareo.acordes if a[0] % PULSOS_POR_COMPAS == 0][:compases] or tarareo.acordes[:1]
        while len(primeros) < compases:
            primeros.append(primeros[-1])
        return [Acorde(inicio + k * PULSOS_POR_COMPAS, inicio + (k + 1) * PULSOS_POR_COMPAS, a[2], a[3], a[4])
                for k, a in enumerate(primeros)]
    grados = progresion_b if nombre == "B" else CIERRE[modo]
    acordes = []
    for k in range(compases):
        grado = grados[k % len(grados)]
        fund, cal = _acorde_por_grado(grado, tonica, modo)
        acordes.append(Acorde(inicio + k * PULSOS_POR_COMPAS, inicio + (k + 1) * PULSOS_POR_COMPAS, fund, cal, grado))
    return acordes


def _acorde_en(acordes: list[Acorde], t: float) -> Acorde | None:
    for a in acordes:
        if a.inicio - 1e-6 <= t < a.fin - 1e-6:
            return a
    return None


# ----------------------------------------------------------------------------
# Melodía, segunda voz y gancho
# ----------------------------------------------------------------------------

def transponer_diatonico(nota: int, grados: int, tonica: int, modo: str) -> int:
    """Mueve una nota `grados` pasos dentro de la escala (no semitonos fijos)."""
    escala = ESCALA_MENOR if modo == "menor" else ESCALA_MAYOR
    relativa = (nota - tonica) % 12
    indice = max(i for i, s in enumerate(escala) if s <= relativa)
    destino = indice + grados
    octavas, indice_destino = divmod(destino, len(escala))
    return nota + (escala[indice_destino] + 12 * octavas) - escala[indice] - (relativa - escala[indice])


def _desplazamiento_registro(tarareo: _Tarareo, programa: int) -> int:
    alturas = [n for n, *_ in tarareo.cuerpo + tarareo.entrada]
    centro = CENTRO_REGISTRO.get(programa, CENTRO_POR_DEFECTO)
    return 12 * round((centro - float(np.median(alturas))) / 12)


def _sin_superposicion(eventos: list[Evento]) -> list[Evento]:
    """Una línea melódica no puede pisarse a sí misma: cada nota se corta donde empieza la siguiente."""
    eventos = sorted(eventos, key=lambda e: e.inicio)
    if not eventos:
        return []
    recortados = []
    for actual, siguiente in zip(eventos, eventos[1:] + [None], strict=True):
        if siguiente is not None and actual.inicio + actual.duracion > siguiente.inicio:
            actual = replace(actual, duracion=max(0.05, siguiente.inicio - actual.inicio))
        recortados.append(actual)
    return recortados


def eventos_melodia(secciones: list[tuple[str, float, int, float]], tarareo: _Tarareo, programa: int,
                    tonica: int, modo: str, acordes: list[Acorde]) -> list[Evento]:
    octavas = _desplazamiento_registro(tarareo, programa)
    escala = ESCALA_MENOR if modo == "menor" else ESCALA_MAYOR
    eventos: list[Evento] = []
    for nombre, inicio, compases, energia in secciones:
        if nombre in SECCIONES_A:
            for nota, posicion, duracion, velocidad in tarareo.entrada + tarareo.cuerpo:
                eventos.append(Evento("melodia", nota + octavas, inicio + posicion, duracion,
                                      _velocidad(velocidad, energia),
                                      origenPulsos=tarareo.origenes.get((posicion, nota))))
        elif nombre == "B":
            for compas in range(0, compases, 2):  # pregunta y respuesta: motivo, compás libre
                acorde = _acorde_en(acordes, inicio + compas * PULSOS_POR_COMPAS)
                grados = ((acorde.fundamental - tonica) % 12) if acorde else 0
                paso = escala.index(grados) if grados in escala else 0
                for nota, posicion, duracion, velocidad in tarareo.motivo():
                    eventos.append(Evento("melodia", transponer_diatonico(nota, paso, tonica, modo) + octavas,
                                          inicio + compas * PULSOS_POR_COMPAS + posicion, duracion,
                                          _velocidad(velocidad, energia)))
        elif nombre == "outro":
            ultima = tarareo.cuerpo[-1][0] + octavas
            tonica_cercana = ultima - ((ultima - tonica) % 12)
            if ultima - tonica_cercana > 6:
                tonica_cercana += 12
            final = inicio + (compases - 1) * PULSOS_POR_COMPAS
            eventos.append(Evento("melodia", tonica_cercana, final, PULSOS_POR_COMPAS, _velocidad(80, energia)))
    return _sin_superposicion(eventos)


def eventos_segunda_voz(secciones: list[tuple[str, float, int, float]], tarareo: _Tarareo,
                        programa_melodia: int, tonica: int, modo: str) -> list[Evento]:
    """
    La melodía que evoluciona, en una pista aparte:
    - intro: anticipa el primer motivo (el "gancho") en el primer compás;
    - A': dobla la melodía a la octava (arriba si entra en registro, si no abajo);
    - A final: canta una tercera diatónica por debajo de la melodía.
    """
    octavas = _desplazamiento_registro(tarareo, programa_melodia)
    notas_a = tarareo.entrada + tarareo.cuerpo
    mas_aguda = max(n for n, *_ in notas_a) + octavas
    doblaje = 12 if mas_aguda + 12 <= NOTA_MAS_AGUDA_SEGUNDA_VOZ else -12
    eventos: list[Evento] = []
    for nombre, inicio, _, energia in secciones:
        if nombre == "intro":
            for nota, posicion, duracion, velocidad in tarareo.motivo():
                eventos.append(Evento("segunda", nota + octavas, inicio + posicion, duracion,
                                      _velocidad(velocidad * 0.6, energia)))
        elif nombre == "A'":
            for nota, posicion, duracion, velocidad in notas_a:
                eventos.append(Evento("segunda", nota + octavas + doblaje, inicio + posicion, duracion,
                                      _velocidad(velocidad * 0.55, energia)))
        elif nombre == "A final":
            for nota, posicion, duracion, velocidad in notas_a:
                tercera = transponer_diatonico(nota + octavas, -2, tonica, modo)
                eventos.append(Evento("segunda", tercera, inicio + posicion, duracion,
                                      _velocidad(velocidad * 0.6, energia)))
    return _sin_superposicion(eventos)


def programa_segunda_voz(estilo: EstiloArreglo, variante: Variante) -> int:
    """El de la tabla, salvo que coincida con el instrumento principal (se oiría como una sola voz)."""
    if estilo.segunda_voz != variante.melodia:
        return estilo.segunda_voz
    return 73 if variante.melodia != 73 else 48


# ----------------------------------------------------------------------------
# Acompañamiento con enlace de voces, bajo con notas de paso, colchón
# ----------------------------------------------------------------------------

def _velocidad(base: float, energia: float) -> int:
    return int(np.clip(round(base * (0.55 + 0.6 * energia)), 1, 127))


def _intervalo_septima(acorde: Acorde) -> int:
    return 10 if acorde.calidad == "menor" or acorde.grado == "V" else 11


def voces_acorde(acorde: Acorde, septima: bool) -> list[int]:
    """Acorde cerrado en posición fundamental en la zona de Do4, con séptima si corresponde."""
    raiz = 60 + acorde.fundamental
    if raiz > 66:
        raiz -= 12
    voces = [raiz, raiz + TERCERA[acorde.calidad], raiz + 7]
    if septima:
        voces.append(raiz + _intervalo_septima(acorde))
    return voces


def _septima_no_choca(acorde: Acorde, melodia: list[Evento]) -> bool:
    """La séptima se agrega solo si la melodía no canta una nota a un semitono de ella."""
    septima = (acorde.fundamental + _intervalo_septima(acorde)) % 12
    for e in melodia:
        if e.inicio < acorde.fin and e.inicio + e.duracion > acorde.inicio:
            distancia = abs(e.nota % 12 - septima) % 12
            if min(distancia, 12 - distancia) == 1:
                return False
    return True


def _inversiones(acorde: Acorde, septima: bool) -> list[list[int]]:
    """Todas las posiciones cerradas del acorde (inversiones) dentro de Sol3-Sol5."""
    base = voces_acorde(acorde, septima)
    candidatas = []
    for octava in (-12, 0, 12):
        for giro in range(len(base)):
            voces = [n + octava for n in sorted(base[giro:] + [n + 12 for n in base[:giro]])]
            if voces[0] >= 55 and voces[-1] <= 79:
                candidatas.append(voces)
    return candidatas or [base]


def _movimiento(voces: list[int], anteriores: list[int]) -> int:
    """Cuánto se mueven las voces: cada nota contra la más cercana del acorde anterior."""
    return sum(min(abs(n - m) for m in anteriores) for n in voces)


def enlazar_voces(acordes: list[Acorde], septimas: set[float]) -> dict[float, list[int]]:
    """
    Para cada acorde (por su inicio), la inversión que menos se mueve respecto
    del anterior: así toca un pianista, sin saltar de posición en cada cambio.
    En empate, la más cercana a Mi4 para que el acompañamiento no se vaya de registro.
    """
    elegidas: dict[float, list[int]] = {}
    anteriores: list[int] | None = None
    for a in acordes:
        candidatas = _inversiones(a, a.inicio in septimas)
        if anteriores is None:
            voces = min(candidatas, key=lambda v: abs(float(np.mean(v)) - 64))
        else:
            voces = min(candidatas, key=lambda v: (_movimiento(v, anteriores), abs(float(np.mean(v)) - 64)))
        elegidas[a.inicio] = voces
        anteriores = voces
    return elegidas


PATRONES_ACOMPANAMIENTO: dict[str, tuple[tuple[float, float, str], ...]] = {
    # (posición en el compás, duración, qué se toca: "acorde", "quinta" o índice de voz)
    "arpegio_lento": tuple((p, 0.95, str((0, 1, 2, 1)[i])) for i, p in enumerate(NEGRAS)),
    "arpegio": tuple((p, 0.5, str((0, 1, 2, 1)[i % 4])) for i, p in enumerate(CORCHEAS)),
    "bloques": ((0.0, 1.9, "acorde"), (2.0, 1.9, "acorde")),
    "bloques_negras": tuple((p, 0.9, "acorde") for p in NEGRAS),
    "quintas_negras": tuple((p, 0.9, "quinta") for p in NEGRAS),
    "quintas": tuple((p, 0.45, "quinta") for p in CORCHEAS),
    "sincopado": ((0.0, 1.4, "acorde"), (1.5, 0.4, "acorde"), (2.5, 1.4, "acorde")),
    "sincopado_lleno": ((0.0, 1.4, "acorde"), (1.5, 0.4, "acorde"), (2.5, 0.9, "acorde"), (3.5, 0.4, "acorde")),
    "rasgueo_simple": tuple((p, 0.9, "acorde") for p in NEGRAS),
    "rasgueo": ((0.0, 0.45, "acorde"), (1.0, 0.45, "acorde"), (1.5, 0.4, "acorde"),
                (2.5, 0.4, "acorde"), (3.0, 0.45, "acorde"), (3.5, 0.4, "acorde")),
    "ostinato": tuple((p, 0.45, str((0, 2, 3, 2)[i % 4])) for i, p in enumerate(CORCHEAS)),
    "contratiempo": tuple((p, 0.35, "acorde") for p in CONTRATIEMPOS),
    "corcheas_acorde": tuple((p, 0.35, "acorde") for p in CORCHEAS),
    "ostinato_lleno": tuple((p, 0.45, str((0, 2, 3, 2)[i % 4])) for i, p in enumerate(CORCHEAS))
    + ((0.0, 3.9, "acorde"),),
}


def eventos_acompanamiento(acordes: list[Acorde], secciones, estilo: EstiloArreglo,
                           voces_por_acorde: dict[float, list[int]], familia: str = "base") -> list[Evento]:
    eventos = []
    for nombre, inicio, compases, energia in secciones:
        if nombre == "outro":
            patron = ((0.0, 3.9, "acorde"),)  # acordes enteros: la canción se apaga
        elif energia >= ENERGIA_PATRON_LLENO:
            patron = PATRONES_ACOMPANAMIENTO[estilo.acompanamiento_lleno]
        else:
            patron = PATRONES_ACOMPANAMIENTO[estilo.acompanamiento]
        if nombre != "outro":
            patron = adaptar_acompanamiento(patron, familia)
        for compas in range(compases):
            base = inicio + compas * PULSOS_POR_COMPAS
            for posicion, duracion, que in patron:
                t = base + posicion
                acorde = _acorde_en(acordes, t)
                if acorde is None:
                    continue
                voces = voces_por_acorde[acorde.inicio]
                if que == "acorde":
                    notas = voces
                elif que == "quinta":  # power chord: siempre desde la fundamental
                    raiz = 48 + acorde.fundamental
                    if raiz > 54:
                        raiz -= 12
                    notas = [raiz, raiz + 7, raiz + 12]
                else:
                    indice = int(que)
                    notas = [voces[indice] if indice < len(voces) else voces[0] + 12]
                duracion = min(duracion, acorde.fin - t)
                for n in notas:
                    eventos.append(Evento("acompanamiento", n, t, duracion, _velocidad(78, energia)))
    return eventos


def _raiz_bajo(fundamental: int) -> int:
    raiz = 36 + fundamental
    return raiz - 12 if raiz > 43 else raiz


def eventos_bajo(acordes: list[Acorde], secciones, estilo: EstiloArreglo) -> list[Evento]:
    """
    Fundamental del acorde según el patrón del estilo. Con `bajo_con_paso`, el
    último golpe corto antes de un cambio de acorde se reemplaza por una nota
    de aproximación cromática (un semitono antes de la nueva fundamental,
    viniendo desde donde está el bajo): así el bajo "conduce" al acorde siguiente.
    """
    eventos = []
    for nombre, inicio, compases, energia in secciones:
        for compas in range(compases):
            base = inicio + compas * PULSOS_POR_COMPAS
            golpes = ((0.0, 4.0, 0),) if nombre == "outro" else estilo.bajo
            posiciones = {p for p, _, _ in golpes}
            # Si el acorde cambia a mitad de compás y el patrón no toca ahí, se agrega un golpe.
            extras = [(a.inicio - base, 2.0, 0) for a in acordes
                      if base < a.inicio < base + PULSOS_POR_COMPAS and (a.inicio - base) not in posiciones]
            for posicion, duracion, intervalo in tuple(golpes) + tuple(extras):
                t = base + posicion
                acorde = _acorde_en(acordes, t)
                if acorde is None:
                    continue
                nota = _raiz_bajo(acorde.fundamental) + intervalo
                siguiente = _acorde_en(acordes, acorde.fin)
                es_ultimo_golpe = duracion <= 0.5 and math.isclose(t, acorde.fin - 0.5, abs_tol=1e-6)
                if (estilo.bajo_con_paso and nombre != "outro" and es_ultimo_golpe
                        and siguiente is not None and siguiente.fundamental != acorde.fundamental):
                    destino = _raiz_bajo(siguiente.fundamental)
                    nota = destino - 1 if destino > _raiz_bajo(acorde.fundamental) else destino + 1
                eventos.append(Evento("bajo", nota, t, min(duracion, acorde.fin - t), _velocidad(85, energia)))
    return eventos


def eventos_colchon(acordes: list[Acorde], secciones, siempre: bool,
                    voces_por_acorde: dict[float, list[int]]) -> list[Evento]:
    eventos = []
    for _, inicio, compases, energia in secciones:
        if not siempre and energia < ENERGIA_PATRON_LLENO:
            continue
        fin = inicio + compases * PULSOS_POR_COMPAS
        for a in acordes:
            if inicio <= a.inicio < fin:
                for n in voces_por_acorde[a.inicio][:3]:
                    eventos.append(Evento("colchon", n - 12, a.inicio, a.fin - a.inicio, _velocidad(55, energia)))
    return eventos


# ----------------------------------------------------------------------------
# Batería con redobles y platillos de transición
# ----------------------------------------------------------------------------

def eventos_bateria(estilo: EstiloArreglo, secciones) -> list[Evento]:
    """
    El patrón del estilo, más:
    - un REDOBLE en los tiempos 3-4 del último compás de cada sección con
      batería (anuncia el cambio), con intensidad que sube;
    - un PLATILLO en el primer tiempo de cada sección con batería;
    - en el outro, un platillo sobre el acorde final.
    """
    eventos = []
    hay_bateria = any(e >= estilo.energia_bateria for *_, e in secciones)
    for indice, (nombre, inicio, compases, energia) in enumerate(secciones):
        if not estilo.bateria:
            continue
        if nombre == "outro":
            if hay_bateria:
                eventos.append(Evento("bateria", PLATILLO, inicio + (compases - 1) * PULSOS_POR_COMPAS, 2.0,
                                      _velocidad(90, 0.8)))
            continue
        if energia < estilo.energia_bateria:
            continue
        eventos.append(Evento("bateria", PLATILLO, inicio, 2.0, _velocidad(85, energia)))
        hay_siguiente = indice + 1 < len(secciones)
        for compas in range(compases):
            base = inicio + compas * PULSOS_POR_COMPAS
            con_redoble = hay_siguiente and compas == compases - 1 and estilo.redoble
            for nota, posiciones in estilo.bateria.items():
                for p in posiciones:
                    if con_redoble and p >= 2.0:
                        continue  # los tiempos 3-4 los ocupa el redoble
                    swing = 0.08 if estilo.swing and (p * 2) % 2 == 1 else 0.0
                    acento = 1.0 if p % 1 == 0 else 0.8
                    eventos.append(Evento("bateria", nota, base + p + swing, 0.2, _velocidad(80 * acento, energia)))
            if con_redoble:
                for nota, posiciones in estilo.redoble.items():
                    for p in posiciones:
                        subida = 0.85 + 0.2 * (p - 2.0)  # de 0.85 a 1.2 a lo largo del redoble
                        eventos.append(Evento("bateria", nota, base + p, 0.2, _velocidad(80 * subida, energia)))
    return eventos


# ----------------------------------------------------------------------------
# Dinámica: crescendo, ritardando y fermata
# ----------------------------------------------------------------------------

def aplicar_crescendo(eventos: list[Evento], secciones) -> list[Evento]:
    """Los 2 compases antes de A' y A final suben de intensidad (hasta +25 %)."""
    rampas = [
        (inicio - COMPASES_CRESCENDO * PULSOS_POR_COMPAS, inicio)
        for nombre, inicio, _, _ in secciones
        if nombre in ("A'", "A final") and inicio >= COMPASES_CRESCENDO * PULSOS_POR_COMPAS
    ]
    resultado = []
    for e in eventos:
        factor = 1.0
        for desde, hasta in rampas:
            if desde <= e.inicio < hasta:
                factor = 1.0 + SUBIDA_CRESCENDO * (e.inicio - desde) / (hasta - desde)
        resultado.append(replace(e, velocidad=int(np.clip(round(e.velocidad * factor), 1, 127))))
    return resultado


def aplicar_ritardando(eventos: list[Evento], inicio_outro: float, compases_outro: int) -> list[Evento]:
    """
    El outro frena: el tempo baja de a poco hasta un 25 % al final, y el
    acorde final se sostiene 2 pulsos de más (fermata).

    El MIDI se escribe a tempo constante, así que el ritardando se aplica
    estirando las posiciones del outro: τ(x) = x + k·x²/(2L), donde x es la
    distancia al inicio del outro, L su largo y k = RITARDANDO.
    """
    largo = compases_outro * PULSOS_POR_COMPAS
    ultimo_compas = inicio_outro + largo - PULSOS_POR_COMPAS

    def estirar(t: float) -> float:
        x = t - inicio_outro
        if x <= 0:
            return t
        if x <= largo:
            return inicio_outro + x + RITARDANDO * x * x / (2 * largo)
        return inicio_outro + largo * (1 + RITARDANDO / 2) + (x - largo) * (1 + RITARDANDO)

    resultado = []
    for e in eventos:
        inicio, fin = estirar(e.inicio), estirar(e.inicio + e.duracion)
        if e.pista != "bateria" and e.inicio >= ultimo_compas - 1e-6 and e.duracion >= 2.0:
            fin += FERMATA_PULSOS
        resultado.append(replace(e, inicio=inicio, duracion=fin-inicio))
    return resultado


def _humanizar(eventos: list[Evento], huella: int) -> list[Evento]:
    """Pequeñas variaciones de intensidad (±4), deterministas por la huella de la melodía."""
    rng = np.random.default_rng(huella)
    variaciones = rng.integers(-4, 5, len(eventos))
    return [replace(e, inicio=round(e.inicio, 4), duracion=round(e.duracion, 4),
                    velocidad=int(np.clip(e.velocidad + v, 1, 127)))
            for e, v in zip(eventos, variaciones, strict=True)]


# ----------------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------------

def arreglar(analisis: AnalisisMusical, armonia: AnalisisArmonia, estilo: EstiloInferido,
             variante: str | None = None, con_estribillo: bool = False,
             variedad_ritmica: bool = False, clima: ClimaMusical | None = None,
             instrumentacion_ampliada: bool = False) -> ResultadoArreglo:
    """
    Arma la canción completa. `variante` fuerza una variante (para tests y
    pruebas); en el pipeline se elige sola.
    """
    tonica, modo = leer_tonalidad(analisis.tonalidad)
    config_estilo = ESTILOS[estilo.preset]
    huella = huella_melodia(analisis)
    familia = "base"
    if variedad_ritmica:
        config_estilo, familia = variar_patrones(config_estilo, huella)
    elegida = elegir_variante(estilo.preset, estilo.rasgos, huella, variante)
    progresion_b = elegir_progresion_b(modo, huella)
    tarareo = preparar_tarareo(analisis, armonia)
    gancho = detectar_gancho(analisis.melodiaCuantizada) if con_estribillo else None

    plan = planificar_estructura(tarareo.compases, analisis.bpm)
    secciones: list[tuple[str, float, int, float]] = []
    compas_actual = 0
    for nombre, compases in plan:
        secciones.append((nombre, float(compas_actual * PULSOS_POR_COMPAS), compases, ENERGIA[nombre]))
        compas_actual += compases

    acordes: list[Acorde] = []
    tarareos = {}
    for nombre, inicio, compases, _ in secciones:
        local = (_tarareo_estribillo(tarareo, gancho, armonia.anacrusaPulsos, compases)
                 if gancho and nombre in ("A'", "A final") else tarareo)
        tarareos[inicio] = local
        acordes += acordes_de_seccion(nombre, inicio, compases, local, tonica, modo, progresion_b)

    melodia = _sin_superposicion([e for s in secciones for e in eventos_melodia(
        [s], tarareos[s[1]], elegida.melodia, tonica, modo, acordes)])
    segunda = [e for s in secciones for e in eventos_segunda_voz(
        [s], tarareos[s[1]], elegida.melodia, tonica, modo)]
    septimas = {a.inicio for a in acordes if config_estilo.septimas and _septima_no_choca(a, melodia + segunda)}
    voces_por_acorde = enlazar_voces(acordes, septimas)
    eventos = (
        melodia
        + segunda
        + eventos_acompanamiento(acordes, secciones, config_estilo, voces_por_acorde, familia)
        + eventos_bajo(acordes, secciones, config_estilo)
        + eventos_bateria(config_estilo, secciones)
    )

    pistas = [
        PistaArreglo(nombre="Melodía", rol="melodia", programa=elegida.melodia),
        PistaArreglo(nombre="Segunda voz", rol="segunda", programa=programa_segunda_voz(config_estilo, elegida)),
        PistaArreglo(nombre="Acompañamiento", rol="acompanamiento", programa=elegida.acompanamiento),
        PistaArreglo(nombre="Bajo", rol="bajo", programa=elegida.bajo),
    ]
    if elegida.colchon is not None and not instrumentacion_ampliada:
        eventos += eventos_colchon(acordes, secciones, config_estilo.colchon_siempre, voces_por_acorde)
        pistas.append(PistaArreglo(nombre="Colchón", rol="colchon", programa=elegida.colchon))
    if config_estilo.bateria:
        pistas.append(PistaArreglo(nombre="Batería", rol="bateria", programa=0, bateria=True))

    if instrumentacion_ampliada:
        eventos, colores = ampliar_instrumentacion(
            estilo.preset, elegida, acordes, secciones, voces_por_acorde, eventos, clima)
        pistas.extend(colores)
    if clima:
        factor = 0.78 + 0.30 * clima.intensidad
        eventos = [replace(e, velocidad=max(1, min(127, round(e.velocidad * factor))))
                   if e.pista != "melodia" else e for e in eventos]

    nombre_outro, inicio_outro, compases_outro, _ = secciones[-1]
    eventos = aplicar_crescendo(eventos, secciones)
    if nombre_outro == "outro":
        eventos = aplicar_ritardando(eventos, inicio_outro, compases_outro)
    eventos = _humanizar(sorted(eventos, key=lambda e: (e.inicio, e.pista, e.nota)), huella)
    fin_pulsos = max(e.inicio + e.duracion for e in eventos)
    duracion = fin_pulsos * 60.0 / analisis.bpm

    arreglo = ArregloCancion(
        variante=elegida.nombre,
        bpm=analisis.bpm,
        compases=compas_actual,
        duracionSegundos=round(duracion, 2),
        septimas=bool(septimas),
        progresionB=list(progresion_b),
        estructura=[SeccionArreglo(nombre=n, compasInicio=int(i // PULSOS_POR_COMPAS), compases=c, energia=e)
                    for n, i, c, e in secciones],
        pistas=pistas,
        gancho=gancho,
        patronRitmico=familia,
        clima=clima,
    )
    if gancho:
        funciones = {"A": "verso", "A'": "estribillo", "A final": "estribillo final", "B": "puente"}
        for seccion in arreglo.estructura:
            seccion.funcion = funciones.get(seccion.nombre, seccion.nombre)
    logger.info(
        "Arreglo %s/%s: %s, B=%s, %d compases, %.0f s, %d notas",
        estilo.preset, elegida.nombre, " → ".join(n for n, *_ in secciones), "-".join(progresion_b),
        compas_actual, duracion, len(eventos),
    )
    return ResultadoArreglo(arreglo=arreglo, eventos=eventos)
