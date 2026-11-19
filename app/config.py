"""
Configuración del worker por variables de entorno.

Usa pydantic-settings para que cada valor tenga un default razonable para
desarrollo local, pero se pueda pisar con variables de entorno (o un
archivo .env) cuando esto corra en Docker junto a los otros workers.

Todas las variables van prefijadas con TARAREO_ para no chocar con las de
los otros 4 workers si en algún momento comparten un mismo entorno.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TARAREO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Identidad del worker -----------------------------------------
    version: str = "0.1.0"
    nivel_log: str = "INFO"

    # --- Modo desarrollo ------------------------------------------------
    # Solo en desarrollo se aceptan rutas locales o file:// en inputUrls
    # (probar sin storage). En producción el worker recibe únicamente URLs
    # http(s) prefirmadas de R2: aceptar rutas locales ahí permitiría que
    # quien llame al worker le haga leer cualquier archivo del contenedor.
    # Por eso el default es False (seguro por defecto) y se activa en .env.
    modo_desarrollo: bool = False

    # --- Control de carga -----------------------------------------------
    # Jobs que el worker procesa a la vez. Si llega uno más, /procesar
    # responde 503 y Django reintenta más tarde (decisión 6 de
    # docs/ARQUITECTURA.md). Cada job de basic-pitch con TensorFlow usa
    # varios núcleos y unos cientos de MB de RAM: 2 es un valor prudente
    # para una máquina de desarrollo; ajustarlo midiendo en el servidor.
    capacidad: int = Field(default=2, gt=0)

    # --- Descarga de la entrada (ingesta.py) ------------------------------
    # 30 s de audio comprimido pesan menos de 1 MB; un WAV sin comprimir,
    # unos 5 MB. 25 MB deja mucho margen y corta archivos absurdos antes
    # de llenar el disco.
    descarga_tamano_maximo_mb: float = Field(default=25.0, gt=0)
    descarga_timeout_segundos: float = Field(default=30.0, gt=0)

    # --- Directorios de trabajo -----------------------------------------
    # Todo archivo intermedio o de salida (WAV normalizado, MIDI, analisis.json)
    # vive bajo este directorio, nunca en rutas hardcodeadas. Coincide con
    # "salidas/" del .gitignore.
    directorio_salidas: Path = Path("salidas")

    # --- Ingesta / formato de audio destino ------------------------------
    frecuencia_muestreo_hz: int = 22050

    # --- Validación de duración (preprocesado.py) ------------------------
    # Por debajo de esto la deteccion de tempo no es confiable; por encima,
    # el tarareo deja de ser una "semilla" util (ver CLAUDE.md).
    duracion_minima_segundos: float = 8.0
    duracion_maxima_segundos: float = 30.0

    # --- Validación de señal (preprocesado.py) ---------------------------
    # Umbral de silencio en dBFS: por debajo de esto se considera silencio.
    umbral_silencio_dbfs: float = -45.0

    # --- Validez de la melodía detectada (melodia.py) --------------------
    # Umbral de confianza promedio (amplitud que devuelve basic-pitch, 0-1)
    # por debajo del cual se considera que no hay una melodía clara (ruido).
    # Distinto de limpieza_amplitud_minima: este es un corte a nivel job
    # (¿el audio entero sirve?), no a nivel nota individual.
    # Calibrado con UN solo dato de cada lado, hace falta más para afinarlo:
    # ruido blanco sintético (anoisesrc) dio confianza 0.306 con 4 notas;
    # tarareo real (mi_tarareo.wav) dio 0.550 con 34 notas. 0.42 deja margen
    # de ambos lados, pero es provisorio.
    melodia_confianza_minima: float = 0.42
    # Segunda opinión de altura sobre la señal, sin limitarse a una escala.
    interpretacion_verificar_alturas: bool = True
    analisis_ritmo_fiel: bool = True
    # Expresión moderada: mantener el gesto sin reproducir toda la inestabilidad.
    expresion_intensidad: float = Field(default=0.4, ge=0, le=1)

    # --- Limpieza de notas (limpieza.py), valores medidos en CLAUDE.md ---
    limpieza_semitonos_octava: int = 12
    limpieza_hueco_fusion_ms: float = 50.0
    limpieza_margen_octavas_mediana: float = 1.0
    limpieza_amplitud_minima: float = 0.40
    limpieza_duracion_minima_ms: float = 80.0

    # --- Análisis musical (analisis.py, etapa 5) ---------------------------
    # Rango de tempos que se consideran. Fuera de esto, un tarareo casi
    # siempre es el doble o la mitad del tempo "sentido".
    analisis_bpm_minimo: float = 60.0
    analisis_bpm_maximo: float = 160.0
    # Centro de la preferencia suave de tempo (en octavas, desvío de 1). Solo
    # desempata entre un tempo y su doble/mitad cuando las notas encajan igual
    # de bien en ambos; no fuerza ningún valor.
    analisis_bpm_preferido: float = 100.0
    # Menos notas que esto no alcanzan para entender pulso ni tonalidad.
    analisis_notas_minimas: int = 4
    # Cuantización suave: una nota se ajusta a la grilla de semicorcheas solo
    # si está a menos de esta fracción de la celda. Si no, se respeta como se
    # cantó (es intención, no error).
    analisis_tolerancia_cuantizacion: float = Field(default=0.30, gt=0, le=0.5)

    # --- Render (render.py, etapa 8) ---------------------------------------
    # FluidSynth y el SoundFont NO van en el repo (binario y ~140 MB). Si no
    # se configuran, se buscan en `directorio_herramientas` (desarrollo local)
    # y, para FluidSynth, en el PATH. En Docker se fijan por variable de
    # entorno (TARAREO_FLUIDSYNTH, TARAREO_SOUNDFONT). Si se configuran y no
    # existen, es un error: no se busca otra cosa por detrás.
    fluidsynth: str | None = None
    soundfont: Path | None = None
    directorio_herramientas: Path = Path("herramientas")
    # Ganancia de FluidSynth: baja para que la mezcla no sature antes de
    # normalizar (el volumen final lo fija la medición ebur128 + ganancia).
    render_ganancia: float = Field(default=0.5, gt=0, le=2)
    # -16 LUFS: el nivel de referencia de Apple Music (Spotify/YouTube usan
    # -14). Se bajó de -14 a -16 el 2026-11-14 tras la primera escucha
    # ("bajarlo un poco"). Picos ≤ -1 dBTP para que no distorsione al
    # convertirse a MP3 o al reproducirse.
    render_lufs_objetivo: float = -16.0
    render_pico_maximo_dbtp: float = -1.0
    render_bitrate_kbps: int = 192
    # Después de la última nota se deja sonar la reverb y se baja en fade.
    render_cola_segundos: float = Field(default=2.5, ge=0)
    # Acabado suave (EQ + compresor estéreo, reverb moderada en FluidSynth).
    # false permite comparar con el render anterior al mismo loudness.
    render_masterizacion: bool = True

    # --- Versiones de la canción ------------------------------------------
    # 1 = solo la principal. Hasta 3: la principal + 2 alternativas en otros
    # estilos que también encajan con el tarareo (el usuario elige escuchando).
    # Cada alternativa suma ~5-6 s de CPU (arreglo + render).
    versiones_maximas: int = Field(default=3, ge=1, le=3)
    muestra_segundos: float = Field(default=16.0, ge=10, le=20)
    melodia_expresiva: bool = True
    arreglo_con_estribillo: bool = True
    arreglo_variedad_ritmica: bool = True
    arreglo_clima_musical: bool = True
    arreglo_instrumentacion_ampliada: bool = True

    # --- Callback al backend ---------------------------------------------
    # El callback es una notificación, no una dependencia: si falla o da
    # timeout, se registra en el log y el job igual queda COMPLETADO.
    callback_timeout_segundos: float = 5.0
    # Se usa solo si la solicitud no trae su propio callbackUrl.
    callback_url_default: str | None = None
    # Secreto compartido con Django: va en el header X-Worker-Token de cada
    # callback para que Django rechace callbacks falsos (decisión 14). El
    # worker sale a internet (R2), así que el aislamiento de red ya no
    # alcanza. SecretStr: nunca aparece en logs ni en repr().
    callback_token: SecretStr | None = None
    # El callback FINAL se reintenta (con espera creciente: 1 s, 2 s, 4 s...)
    # si falla por red o por un 5xx de Django. Los de progreso no: si se
    # pierde uno, el siguiente lo reemplaza.
    callback_reintentos: int = Field(default=3, ge=0, le=10)

    # --- Subida a R2 (almacenamiento.py) ----------------------------------
    subida_timeout_segundos: float = Field(default=60.0, gt=0)
    subida_reintentos: int = Field(default=3, ge=0, le=10)

    # --- Retención (deuda técnica 4) ----------------------------------------
    # Jobs terminados que se recuerdan para GET /jobs/{id}. Django recibe el
    # resultado por callback; esto es solo el respaldo de polling.
    retencion_jobs_minutos: float = Field(default=60.0, gt=0)
    maximo_jobs_en_memoria: int = Field(default=1000, gt=0)
    # Carpetas de jobs en salidas/ (solo quedan en desarrollo: con
    # outputUploadUrls se borran al subir). Se borran las más viejas que esto.
    retencion_salidas_horas: float = Field(default=24.0, gt=0)

    @property
    def descarga_tamano_maximo_bytes(self) -> int:
        return int(self.descarga_tamano_maximo_mb * 1024 * 1024)

    def directorio_job(self, job_id: UUID) -> Path:
        """
        Carpeta de trabajo de un job puntual, bajo directorio_salidas.

        Cada job tiene su propia carpeta (en vez de archivos sueltos con
        nombres generados) para que jobs concurrentes no puedan pisarse
        archivos entre sí, y para que outputUrls apunte a algo predecible.

        Recibe un UUID ya validado, nunca un texto libre: el nombre de la
        carpeta sale de `str(job_id)` (hex y guiones), así que un jobId como
        "../../etc" no puede escapar de directorio_salidas.
        """
        return self.directorio_salidas / str(UUID(str(job_id)))


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Instancia única y cacheada de la configuración (se lee una sola vez)."""
    return Configuracion()
