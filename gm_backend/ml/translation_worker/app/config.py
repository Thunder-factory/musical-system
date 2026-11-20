"""Configuración del worker: todo se lee de variables de entorno o de .env."""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent  # carpeta worker-traduccion/


@dataclass(frozen=True)
class NivelLlm:
    """Una entrada del catálogo de LLM: nombre del nivel, modelo de Ollama y VRAM libre que exige."""
    nombre: str
    modelo: str
    vram_min_mb: int


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ / ".env", extra="ignore")

    # Ejecución
    dispositivo: str = "cuda"
    modo_simulado: bool = False
    vram_limite_mb: int = 7700

    # Rutas
    dir_modelos: Path = Path("modelos")
    dir_trabajo: Path = Path("work")
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    # Modo simulado (fase 3): con MODO_SIMULADO=true no se usa GPU, modelos, Ollama ni FFmpeg
    simulado_segundos: float = 10.0  # lo que tarda un trabajo simulado
    simulado_error: str = ""         # ENTRADA_INVALIDA | ERROR_INTERNO: todos los trabajos acaban en ese error

    # API (fase 2)
    latido_s: float = 25.0           # latido al orquestador; el contrato pide 30 s o menos
    cola_max: int = 10               # trabajos en espera; con la cola llena /procesar responde 503
    callback_timeout_s: float = 5.0  # un latido que tarda más se da por perdido (llega el siguiente)
    callback_reintentos: int = 5     # solo para el aviso final (COMPLETADO / ERROR)
    callback_espera_s: float = 2.0   # espera entre reintentos (se duplica cada vez)
    transferencia_timeout_s: float = 300.0  # descarga del video y subida de resultados

    # Límites de entrada
    max_duracion_s: int = 240
    max_tamano_mb: int = 200
    idiomas_soportados: str = "en,es,fr,zh"
    formatos_soportados: str = "mp4,mov,webm"

    # Modelos
    # auto: RoFormer si está instalado y cabe; si no, Demucs (se adapta a cada equipo, como los niveles del LLM)
    separador: str = "auto"  # auto | demucs | roformer (fase 7.2)
    roformer_vram_min_mb: int = 4200  # medido: MelBand ocupa ~3830 MB en la RTX 3070 (más margen)
    demucs_modelo: str = "htdemucs"  # htdemucs | htdemucs_ft (4 modelos: mejor y ~4 veces más lento)
    roformer_modelo: str = "vocals_mel_band_roformer.ckpt"  # en modelos/separacion/
    roformer_python: Path = Path(".venv-rvc/Scripts/python.exe")  # entorno con audio-separator
    roformer_timeout_s: int = 900
    # MusicAI: modelo de audio-separator que quita la reverb de la voz separada (vacío = no se usa).
    # La voz seca es la referencia de timbre (XTTS, Seed-VC) y de melodía; la mezcla final no cambia.
    roformer_dereverb: str = ""
    demucs_semilla: int = 0  # semilla del desplazamiento aleatorio de Demucs; -1 = sin fijar (cada corrida separa distinto)
    whisper_modelo: str = "large-v3"
    whisper_compute: str = "int8_float16"
    whisper_vad: bool = False  # filtro de silencios de Whisper; empeoró la letra en las pruebas
    # MusicAI: segunda pasada sobre los tramos con voz que Whisper dejó sin letra (p. ej. un rap entero)
    whisper_recuperar_tramos: bool = True
    sintetizador: str = "xtts"
    xtts_modelo: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    coqui_tos_agreed: str = "0"
    xtts_reintentos: int = 2  # tomas extra cuando XTTS genera un audio mucho más largo que el texto

    # RVC (fase 7.3): cambia el timbre de la voz sintetizada por el de un modelo entrenado (Applio)
    rvc_activo: bool = False
    rvc_python: Path = Path(".venv-rvc/Scripts/python.exe")  # entorno aparte (requirements-rvc.txt)
    rvc_applio: Path = Path("modelos/rvc/applio")             # Applio 3.7.1 (core.py)
    rvc_modelo: str = ""     # .pth del modelo entrenado
    rvc_indice: str = ""     # .index del modelo (opcional): acerca el timbre al de la grabación
    rvc_tono: int = 0        # semitonos (+12 = una octava arriba)
    rvc_index_rate: float = 0.5  # cuánto pesa el índice (0-1): más = más parecido, pero más artefactos
    rvc_protect: float = 0.33    # protege consonantes y respiraciones (0-0.5)
    rvc_timeout_s: int = 600

    # LLM: catálogo por niveles, de mayor a menor. Formato: nivel=modelo@vram_libre_mínima_mb
    llm_proveedor: str = "ollama"
    llm_url: str = "http://localhost:11434"
    llm_nivel: str = "auto"  # auto | alto | medio | ligero
    # VRAM medida en la RTX 3070 con num_ctx=4096: 9B → 6335 MB, 8B → 5244 MB (el 4B es una estimación)
    llm_niveles: str = "alto=qwen3.5:9b-q4_K_M@6350;medio=qwen3:8b@5250;ligero=qwen3:4b@3000"
    llm_modelo: str = ""  # si se indica, fuerza ese modelo exacto e ignora los niveles
    llm_num_ctx: int = 4096  # alcanza para lotes de 25 versos; subirlo cuesta VRAM
    llm_temperatura: float = 0.2     # baja: traducciones estables entre corridas
    llm_semilla: int = 42            # semilla fija (los reintentos usan semilla+1, +2...)
    llm_resumen: bool = True         # antes de traducir, el modelo resume de qué trata la canción
    llm_revision: bool = True        # segunda pasada: gramática, concordancia y naturalidad
    llm_timeout_s: int = 600

    # Gemini (MusicAI en Modal): LLM_PROVEEDOR=gemini. Los modelos se prueban en orden: si uno está
    # saturado (429/503) o no responde, se usa el siguiente.
    gemini_api_key: str = ""
    gemini_modelos: str = "gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite"
    gemini_razonamiento: str = "low"  # thinkingLevel de los modelos que razonan: low = rápido
    gemini_timeout_s: float = 60.0
    gemini_reintentos: int = 3         # reintentos por modelo antes de pasar al siguiente

    # Letra de LRCLIB (fase 7.1): con titulo (y artista) se busca la letra para corregir a Whisper
    lrclib_activo: bool = True
    lrclib_url: str = "https://lrclib.net"
    lrclib_timeout_s: float = 10.0

    # Calidad de la letra (fase 1.5)
    frase_min_s: float = 1.0         # un verso más corto se une con su vecino (0 = no unir)
    union_hueco_max_s: float = 1.0   # ...salvo que el vecino esté más lejos que esto
    silabas_por_segundo: float = 5.0  # lo que el sintetizador dice sin sonar atropellado; fija el máximo por verso
    conservar_interjecciones: bool = True  # oh, hey, la la...: no se traducen (false = se tratan como letra)
    # qué voz llevan: original (se copian de la canción) | sintetizada (XTTS, mismo timbre que el resto)
    # | auto (sintetizada si sale bien; si no, la original)
    interjecciones: str = "auto"
    interj_tempo_min: float = 0.75   # una interjección sintetizada se estira o acelera poco
    interj_tempo_max: float = 1.4
    reintentos_silabas: int = 2      # veces que se le pide al LLM acortar una frase que se pasa

    # Canto (fase 7, paso 3): Seed-VC convierte la voz sintetizada a la del cantante y con su melodía
    canto_activo: bool = False
    seedvc_dir: Path = Path("modelos/seedvc/seed-vc")
    canto_melodia: str = "original"   # original (la del cantante) | fuente (la de XTTS: solo cambia el timbre)
    canto_pasos: int = 30             # pasos de difusión: más = mejor y más lento (el autor recomienda 30-50)
    canto_cfg: float = 0.7
    canto_semitonos: int = 0
    canto_referencia_s: float = 12.0  # segundos de la voz original que se usan como referencia del timbre
    canto_timeout_s: int = 1200
    # MusicAI: corregir saltos de octava, limitar al rango del cantante y quitar picos de la melodía
    # antes de Seed-VC (reduce los «gallos»).
    canto_limpiar: bool = False

    # Igualar la voz nueva a la original (fase 7, paso 2): ecualización, reverb y nivel
    igualar_voz: bool = True
    igualar_eq_max_db: float = 9.0       # tope de la ecualización por banda
    igualar_reverb_mezcla: float = 0.2   # proporción de reverb (0 = sin reverb)

    # Ajuste de la voz sintetizada y mezcla
    tempo_min: float = 0.8   # como mucho se ralentiza un 20 %
    tempo_max: float = 1.6   # como mucho se acelera un 60 %
    ganancia_voz_db: float = 3.0
    lufs_objetivo: float = -14.0

    # MusicAI: versos que no caben en su tiempo. Orden: 1) pedir al LLM una versión más corta y volver a
    # sintetizarla; 2) acelerar hasta TEMPO_RESCATE; 3) adelantar el inicio dentro del silencio anterior;
    # 4) cortar en una pausa entre palabras; 5) solo si no hay pausa, cortar como antes.
    acortar_desbordes: bool = True
    acortar_timeout_s: float = 90.0  # si el LLM tarda más, se sigue sin acortar (no retiene la GPU)
    tempo_rescate: float = 1.55
    adelanto_max_s: float = 0.25
    recorte_umbral: float = 0.01  # recorte de silencios de cada toma de XTTS (antes 0.02: comía consonantes)
    # MusicAI: mezcla y nivel
    igualar_nivel_por_frase: bool = True  # cada verso al volumen relativo que tiene en la canción original
    igualar_nivel_max_db: float = 6.0
    loudnorm_dos_pasadas: bool = True     # normalización lineal (sin «bombeo» de volumen)
    # MusicAI: compara el resultado con la canción original y avisa de secciones desaparecidas
    validar_resultado: bool = True
    # MusicAI: donde se canta sin palabras reconocibles (ad-libs, «ooh») y no hay verso, voz original
    rellenar_sin_letra: bool = True

    @property
    def idiomas(self) -> list[str]:
        return [i.strip() for i in self.idiomas_soportados.split(",") if i.strip()]

    @property
    def formatos(self) -> list[str]:
        return [f.strip().lower() for f in self.formatos_soportados.split(",") if f.strip()]

    @property
    def catalogo_gemini(self) -> list[str]:
        return [m.strip() for m in self.gemini_modelos.split(",") if m.strip()]

    @property
    def catalogo_llm(self) -> list[NivelLlm]:
        """Niveles del LLM en el orden escrito (el primero es el preferido)."""
        niveles = []
        for parte in self.llm_niveles.split(";"):
            if not parte.strip():
                continue
            nombre, resto = parte.split("=", 1)
            modelo, vram = resto.rsplit("@", 1)
            niveles.append(NivelLlm(nombre.strip(), modelo.strip(), int(vram)))
        return niveles

    def ruta(self, p: Path) -> Path:
        """Convierte una ruta relativa en absoluta respecto a worker-traduccion/."""
        return p if p.is_absolute() else RAIZ / p

    @property
    def ruta_modelos(self) -> Path:
        return self.ruta(self.dir_modelos)

    @property
    def ruta_trabajo(self) -> Path:
        return self.ruta(self.dir_trabajo)


@lru_cache
def obtener_config() -> Config:
    return Config()


def preparar_entorno_modelos(cfg: Config | None = None) -> Path:
    """Hace que todas las librerías guarden sus modelos dentro de DIR_MODELOS.

    Debe llamarse antes de importar torch / TTS / faster_whisper.
    """
    cfg = cfg or obtener_config()
    base = cfg.ruta_modelos
    base.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TORCH_HOME", str(base / "torch"))        # Demucs
    os.environ.setdefault("HF_HOME", str(base / "huggingface"))     # faster-whisper
    os.environ.setdefault("TTS_HOME", str(base))                    # XTTS → modelos/tts
    if cfg.coqui_tos_agreed == "1":
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
    return base
