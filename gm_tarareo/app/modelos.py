"""
Esquemas Pydantic del contrato del worker.

Estos modelos son la interfaz que el resto del equipo (backend Django) consume:
- `SolicitudProcesar` / `RespuestaProcesar` para POST /procesar
- `RespuestaSalud` para GET /salud
- `ResultadoJob` para GET /jobs/{id} y para el payload del callback

También viven acá los modelos de dominio que cruzan entre módulos del
pipeline (`NotaMusical`, `NotaDescartada`, `AnalisisMelodia`), porque son la
"representación intermedia" que un módulo produce y el siguiente consume.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Versión del contrato worker ↔ Django (decisión 13 de docs/ARQUITECTURA.md).
# El JSON Schema de cada versión está en contratos/vN/.
VERSION_CONTRATO = 1

# Archivos que produce el worker y el Content-Type con que se suben a R2. El
# PUT prefirmado tiene que mandar el MISMO Content-Type con que Django firmó
# la URL: si no, R2 rechaza la subida (CLAUDE.md, contrato con el equipo).
#
# Versiones (2026-11-14): además de la canción principal, el worker genera hasta
# 2 alternativas en otros estilos que también encajan con el tarareo, para que
# el usuario elija escuchando. Nombres fijos por posición (no por estilo):
# Django firma las URLs antes de saber qué estilos van a salir.
TIPOS_SALIDA: dict[str, str] = {
    "cancion.mp3": "audio/mpeg",
    "melodia.mid": "audio/midi",
    "arreglo.mid": "audio/midi",
    "analisis.json": "application/json",
    "cancion-2.mp3": "audio/mpeg",
    "arreglo-2.mid": "audio/midi",
    "cancion-3.mp3": "audio/mpeg",
    "arreglo-3.mid": "audio/midi",
    "muestra.mp3": "audio/mpeg",
    "muestra-2.mp3": "audio/mpeg",
    "muestra-3.mp3": "audio/mpeg",
    "partitura.musicxml": "application/vnd.recordare.musicxml+xml",
}


class EstadoJob(str, Enum):
    """Estados válidos de un job, tal como los define el contrato con el equipo."""

    PENDIENTE = "PENDIENTE"
    PROCESANDO = "PROCESANDO"
    COMPLETADO = "COMPLETADO"
    FALLIDO = "FALLIDO"


class CodigoError(str, Enum):
    """
    Si Django debe reintentar un job FALLIDO (decisión 8 de docs/ARQUITECTURA.md).

    - ENTRADA_INVALIDA: definitivo. El audio no sirve (silencio, ruido, muy
      corto, archivo corrupto): reintentar daría lo mismo. Se le muestra el
      `error` al usuario.
    - ERROR_INTERNO: transitorio. Red, URL vencida, falla del servidor: vale
      la pena reintentar (con URLs prefirmadas nuevas).
    """

    ENTRADA_INVALIDA = "ENTRADA_INVALIDA"
    ERROR_INTERNO = "ERROR_INTERNO"


class MotivoFallo(str, Enum):
    """
    Por qué un audio de entrada no sirve para extraer una melodía.

    Cada valor corresponde a una validación distinta en preprocesado.py y a
    un mensaje accionable distinto para el usuario final.
    """

    GRABACION_MUY_CORTA = "GRABACION_MUY_CORTA"
    SIN_SENAL = "SIN_SENAL"
    SIN_MELODIA_CLARA = "SIN_MELODIA_CLARA"


class MotivoDescarte(str, Enum):
    """Por qué limpieza.py descartó o fusionó una nota cruda de basic-pitch."""

    OCTAVA_DUPLICADA = "OCTAVA_DUPLICADA"
    FUSIONADA = "FUSIONADA"
    FUERA_DE_RANGO = "FUERA_DE_RANGO"
    SENAL_DEBIL = "SENAL_DEBIL"


class ParametrosProcesamiento(BaseModel):
    """
    Parámetros que acompañan la solicitud de procesamiento.

    El usuario NO elige género ni instrumentación: el estilo sale del propio
    tarareo (etapa 6.5). Por eso `genero` ya no está en el contrato (se quitó
    el 2026-11-14). `extra="allow"`: si Django manda un campo que el worker no
    conoce (incluido `genero`), se acepta y se ignora en vez de fallar.

    `tempoDeseado` y `duracionObjetivo` se aceptan pero todavía no se usan:
    el tempo sale del tarareo y la duración la fija el arreglo (60-90 s).
    """

    model_config = ConfigDict(extra="allow")

    tempoDeseado: int | None = Field(default=None, gt=0)
    duracionObjetivo: int | None = Field(default=None, gt=0)


class SolicitudProcesar(BaseModel):
    """
    Cuerpo de POST /procesar.

    `callbackUrl` no está en el contrato original tal cual estaba escrito
    (solo listaba jobId/parametros/inputUrls), pero sin él el worker no
    tiene forma de saber a dónde notificar al terminar. Se agrega acá como
    opcional: si no viene, se usa TARAREO_CALLBACK_URL_DEFAULT de config.py,
    y si tampoco hay default, simplemente no se notifica (se loguea y el
    resultado queda disponible igual en GET /jobs/{id}).

    `jobId` es un UUID (cualquier versión; Django genera uuid4 con
    UUIDField). Se valida acá porque el worker lo usa como nombre de
    carpeta: un texto libre permitiría rutas como "../../algo". Un jobId
    que no es UUID se rechaza con 422.

    `outputUploadUrls`: nombre de archivo → URL PUT prefirmada de R2,
    generada por Django AL DESPACHAR (decisión 9). Si viene, el worker sube
    ahí cada salida con su Content-Type de `TIPOS_SALIDA` y después borra su
    copia local. Si no viene (desarrollo), las salidas quedan en disco y
    `outputUrls` trae rutas locales. Django puede pedir solo algunas salidas.
    """

    jobId: UUID
    version: Literal[1] = VERSION_CONTRATO
    parametros: ParametrosProcesamiento = Field(default_factory=ParametrosProcesamiento)
    inputUrls: list[str] = Field(min_length=1)
    outputUploadUrls: dict[str, str] | None = None
    callbackUrl: str | None = None
    operacion: Literal["generar", "muestras", "completar"] = "generar"
    versionElegida: int = Field(default=1, ge=1, le=3)

    @field_validator("outputUploadUrls")
    @classmethod
    def _solo_salidas_conocidas(cls, valor: dict[str, str] | None) -> dict[str, str] | None:
        if valor is not None:
            desconocidas = set(valor) - set(TIPOS_SALIDA)
            if desconocidas:
                raise ValueError(
                    f"Salidas desconocidas: {sorted(desconocidas)}. El worker produce: {sorted(TIPOS_SALIDA)}"
                )
            if not valor:
                raise ValueError("outputUploadUrls no puede estar vacío: omitirlo o pedir al menos una salida")
        return valor


class RespuestaProcesar(BaseModel):
    """Respuesta 202 de POST /procesar."""

    jobId: UUID
    estado: EstadoJob = EstadoJob.PROCESANDO


class RespuestaSalud(BaseModel):
    """
    Respuesta 200 de GET /salud.

    `capacidad` y `ocupados` le permiten a Django saber si conviene
    despachar ahora o esperar (decisión 6 de docs/ARQUITECTURA.md); si
    despacha igual con el worker lleno, recibe 503.
    """

    estado: str = "ok"
    version: str
    modelosCargados: bool
    capacidad: int = Field(gt=0)
    ocupados: int = Field(ge=0)


class PuntoExpresion(BaseModel):
    posicion: float = Field(ge=0, le=1, description="Posición relativa dentro de la nota")
    semitonos: float = Field(ge=-0.35, le=0.35, description="Desviación suave respecto de la nota afinada")


class AjusteAltura(BaseModel):
    inicio: float = Field(ge=0)
    original: int = Field(ge=0, le=127)
    corregida: int = Field(ge=0, le=127)
    motivo: str


class InterpretacionTarareo(BaseModel):
    afinacionReferenciaCents: float
    notasVerificadas: int = Field(ge=0)
    ajustes: list[AjusteAltura] = Field(default_factory=list)
    motivo: str


class NotaMusical(BaseModel):
    """Una nota ya limpia, lista para escribirse a MIDI."""

    nota: int = Field(ge=0, le=127, description="Pitch MIDI (0-127)")
    inicio: float = Field(ge=0, description="Segundos desde el inicio del audio")
    duracion: float = Field(gt=0, description="Duración en segundos")
    velocidad: int = Field(ge=0, le=127, description="Velocity MIDI, de la amplitud detectada")
    expresion: list[PuntoExpresion] = Field(default_factory=list)


class NotaDescartada(BaseModel):
    """Una nota cruda que limpieza.py eliminó o fusionó, con el motivo."""

    nota: int = Field(ge=0, le=127)
    inicio: float
    motivo: MotivoDescarte


class NotaCuantizada(BaseModel):
    """
    Una nota de la melodía ubicada en pulsos (negras), no en segundos.

    Es la forma en que las etapas siguientes (armonía, arreglo) piensan la
    melodía: "empieza en el pulso 2.5 y dura medio pulso". El pulso 0 es el
    de la grilla en `AnalisisMusical.desfasePulsoSegundos`.
    """

    nota: int = Field(ge=0, le=127)
    inicioPulsos: float = Field(ge=0)
    duracionPulsos: float = Field(gt=0)
    velocidad: int = Field(ge=0, le=127)
    ajustada: bool = Field(description="True si se movió a la grilla; False si se respetó como se cantó")
    expresion: list[PuntoExpresion] = Field(default_factory=list)


class AnalisisMusical(BaseModel):
    """
    Resultado de la etapa 5: lo que el sistema entiende del tarareo.

    No identifica ninguna canción: describe la melodía que se cantó (su pulso,
    su tonalidad) para poder generar ritmo y armonía coherentes con ella.
    """

    bpm: float = Field(gt=0, description="Tempo de la melodía, en negras por minuto")
    confianzaBpm: float = Field(
        ge=0, le=1, description="Pulso del tarareo comparado con el azar: 0 = no mejor que notas al azar"
    )
    bpmLibrosa: float | None = Field(default=None, description="Segunda opinión (beat tracking sobre el audio)")
    ritmo: str = Field(description='"medido" (el tarareo tenía pulso) o "libre" (el sistema puso el pulso)')
    motivoRitmo: str = Field(description="Explicación legible de la decisión")
    desfasePulsoSegundos: float = Field(description="Segundo del audio donde cae el pulso 0")
    tonalidad: str = Field(description='Tónica y modo, p. ej. "G major" o "Bb minor"')
    confianzaTonalidad: float = Field(ge=-1, le=1, description="Correlación de Krumhansl-Schmuckler")
    compas: str = "4/4"
    melodiaCuantizada: list[NotaCuantizada]


class AcordeEnTiempo(BaseModel):
    """Un acorde de la progresión, ubicado en la misma línea de pulsos que la melodía."""

    compas: int = Field(ge=0)
    inicioPulsos: float = Field(ge=0)
    duracionPulsos: float = Field(gt=0)
    nombre: str = Field(description='Cifrado americano, p. ej. "G", "Em", "Bb"')
    grado: str = Field(description='Grado en la tonalidad, p. ej. "I", "vi", "V"')
    notas: list[int] = Field(description="Tríada en MIDI (fundamental, tercera, quinta)")
    cobertura: float = Field(ge=0, le=1, description="Fracción ponderada de la melodía de ese tramo que el acorde contiene")


class AnalisisArmonia(BaseModel):
    """
    Resultado de la etapa 6: acordes elegidos para acompañar la melodía tarareada.

    `acordes` es la lista simple del JSON intermedio; `progresion` tiene el
    detalle en el tiempo. `anacrusaPulsos` dice cuántos pulsos de "entrada"
    hay antes del primer tiempo fuerte (0 si la melodía arranca en el 1).
    """

    anacrusaPulsos: float = Field(ge=0, lt=4)
    acordes: list[str]
    progresion: list[AcordeEnTiempo]


class RasgosTarareo(BaseModel):
    """Lo que se mide del tarareo para inferir el estilo (etapa 6.5)."""

    bpm: float = Field(gt=0)
    modo: str = Field(description='"mayor" o "menor"')
    densidad: float = Field(ge=0, description="Notas por tiempo")
    articulacion: float = Field(ge=0, le=1, description="1 = notas ligadas (legato), bajo = cortadas (staccato)")
    rango: int = Field(ge=0, description="Semitonos entre la nota más grave y la más aguda")
    saltos: float = Field(ge=0, le=1, description="Fracción de intervalos mayores a un tono")
    repeticion: float = Field(
        default=0.0, ge=0, le=1,
        description="Fracción de figuras de 4 notas (3 intervalos) que se repiten, aunque estén transpuestas",
    )


class EstiloInferido(BaseModel):
    """
    Resultado de la etapa 6.5: el estilo con que se va a producir la canción.

    Lo decide el sistema a partir de los rasgos del tarareo; el usuario no
    elige género. `motivo` explica la decisión con los rasgos que más pesaron.
    """

    preset: str
    motivo: str
    puntajes: dict[str, float]
    rasgos: RasgosTarareo
    alternativas: list[str] = Field(
        default_factory=list,
        description="Otros estilos que también encajan (puntaje ≥ 0.6), en orden: se generan como versiones 2 y 3",
    )
    confianza: float = Field(ge=0, le=1, description="Qué tan por delante quedó el estilo elegido del segundo")
    alternativa: str = Field(description="El segundo estilo más parecido")
    ambiguo: bool = Field(description="True si el tarareo suena casi igual a dos estilos")
    mensaje: str = Field(description="Texto para mostrarle al usuario")


class ClimaMusical(BaseModel):
    """Orientación compositiva por reglas; no describe emociones de la persona."""

    nombre: Literal["sereno", "melancolico", "luminoso", "energico", "intenso"]
    intensidad: float = Field(ge=0, le=1)
    confianza: float = Field(ge=0, le=1, description="Separación entre reglas, no probabilidad calibrada")
    ambiguo: bool
    motivo: str


class SeccionArreglo(BaseModel):
    nombre: str = Field(description='"intro", "A", "A\'", "B", "A final" u "outro"')
    compasInicio: int = Field(ge=0)
    compases: int = Field(gt=0)
    energia: float = Field(gt=0, le=1)
    funcion: str | None = None


class GanchoMusical(BaseModel):
    inicioPulsos: float = Field(ge=0)
    duracionPulsos: float = Field(gt=0)
    notas: int = Field(ge=1)
    repetido: bool
    confianza: float = Field(ge=0, le=1)
    motivo: str


class PistaArreglo(BaseModel):
    nombre: str
    rol: str = Field(description='"melodia", "segunda", "acompanamiento", "bajo", "colchon", "bateria", "color1" o "color2"')
    programa: int = Field(ge=0, le=127, description="Programa General MIDI (0-127)")
    bateria: bool = False


class ArregloCancion(BaseModel):
    """
    Resultado de la etapa 7: el plan de la canción completa (lo que está en
    `arreglo.mid`). La sección A es el tarareo; el resto sale de él.
    """

    variante: str
    bpm: float = Field(gt=0)
    compases: int = Field(gt=0)
    duracionSegundos: float = Field(gt=0)
    septimas: bool = Field(description="Si el acompañamiento enriquece los acordes con séptimas")
    progresionB: list[str] = Field(description="Grados de la sección B (una de 3, según el tarareo)")
    estructura: list[SeccionArreglo]
    pistas: list[PistaArreglo]
    gancho: GanchoMusical | None = None
    patronRitmico: str = "base"
    clima: ClimaMusical | None = None


class RenderCancion(BaseModel):
    """Resultado de la etapa 8: el audio final y con qué se hizo."""

    archivo: str = "cancion.mp3"
    duracionSegundos: float = Field(gt=0)
    loudnessLufs: float = Field(description="Loudness integrado de la señal final antes de codificar el MP3")
    picoDbtp: float = Field(description="Pico real (true peak) de la señal antes de codificar el MP3")
    bitrateKbps: int = Field(gt=0)
    soundfont: str = Field(description="Archivo .sf2 usado")
    licenciaSoundfont: str
    masterizacion: str = Field(
        default="desactivada", description="Perfil de acabado aplicado al audio (suave-v1 o desactivada)",
    )


class VersionCancion(BaseModel):
    """Una de las versiones de la canción (1 = la principal, 2 y 3 = alternativas en otros estilos)."""

    numero: int = Field(ge=1, le=3)
    estilo: str = Field(description="Preset de la etapa 6.5 (lofi, balada...)")
    puntaje: float = Field(ge=0, le=1, description="Qué tan bien encaja ese estilo con el tarareo")
    variante: str
    cancion: str = Field(description='Archivo MP3, p. ej. "cancion-2.mp3"')
    arreglo: str = Field(description='Archivo MIDI, p. ej. "arreglo-2.mid"')
    duracionSegundos: float = Field(gt=0)
    loudnessLufs: float
    tipo: Literal["muestra", "completa"] = "completa"
    duracionCompletaSegundos: float | None = None


class AnalisisMelodia(BaseModel):
    """
    El `analisis.json`: resultado de las etapas 3-8 (melodía, limpieza,
    análisis musical, armonía, estilo inferido, arreglo y render).
    """

    melodia: list[NotaMusical]
    confianza: float = Field(ge=0, le=1, description="Confianza promedio de basic-pitch")
    duracionAudioSegundos: float = Field(gt=0)
    notasCrudas: int = Field(ge=0, description="Notas devueltas por basic-pitch antes de limpiar")
    notasFinales: int = Field(ge=0, description="Notas que quedaron después de limpiar")
    notasDescartadas: list[NotaDescartada] = Field(default_factory=list)
    interpretacion: InterpretacionTarareo | None = None
    analisis: AnalisisMusical
    armonia: AnalisisArmonia
    estilo: EstiloInferido
    arreglo: ArregloCancion
    render: RenderCancion
    versiones: list[VersionCancion] = Field(
        default_factory=list, description="La principal y las alternativas generadas, en orden",
    )


class ResultadoJob(BaseModel):
    """
    Estado/resultado de un job.

    Se usa tanto como respuesta de GET /jobs/{id} como cuerpo del callback
    POST {callbackUrl} — es la misma información en ambos casos, solo cambia
    el canal por el que se entrega.
    """

    jobId: UUID
    estado: EstadoJob
    progreso: int = Field(ge=0, le=100)
    etapa: str | None = Field(default=None, description="Etapa en curso (o la última) del pipeline")
    outputUrls: list[str] = Field(default_factory=list)
    error: str | None = None
    codigoError: CodigoError | None = Field(default=None, description="Solo si FALLIDO: si conviene reintentar")
    metadatos: dict | None = None
