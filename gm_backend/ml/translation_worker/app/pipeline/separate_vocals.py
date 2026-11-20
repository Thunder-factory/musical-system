"""Etapa 2 — separar voz e instrumental.

SEPARADOR=demucs (por defecto): Demucs en el proceso del worker (DEMUCS_MODELO: htdemucs | htdemucs_ft).
SEPARADOR=roformer (fase 7.2): un modelo RoFormer (audio-separator) en el entorno aparte .venv-rvc,
llamado como proceso; ver scripts/externos/separar_roformer.py.
"""
import logging
import random
import subprocess
from pathlib import Path

from app.config import RAIZ, Config, obtener_config, preparar_entorno_modelos
from app.errores import ErrorPipeline
from app.gpu import info_gpu, liberar_vram

log = logging.getLogger("worker.separar")

SEPARADORES = ("demucs", "roformer")
SCRIPT_ROFORMER = RAIZ / "scripts" / "externos" / "separar_roformer.py"


def roformer_instalado(cfg: Config) -> bool:
    return cfg.ruta(cfg.roformer_python).is_file() and (cfg.ruta_modelos / "separacion" / cfg.roformer_modelo).is_file()


def elegir_separador(cfg: Config) -> tuple[str, str | None]:
    """SEPARADOR=auto → RoFormer si está instalado y cabe en la VRAM libre; si no, Demucs.

    Devuelve (separador, motivo); el motivo explica por qué no se usó RoFormer (None si se usó o no se pidió auto).
    """
    if cfg.separador != "auto":
        return cfg.separador, None
    if not roformer_instalado(cfg):
        return "demucs", "RoFormer no está instalado (.venv-rvc o el modelo en modelos/separacion)"
    if cfg.dispositivo != "cuda":
        return "demucs", "sin GPU"
    gpu = info_gpu()
    libre = max(0, min(gpu["vram_libre_mb"], cfg.vram_limite_mb - gpu["vram_usada_mb"]))
    if libre < cfg.roformer_vram_min_mb:
        return "demucs", f"RoFormer necesita unos {cfg.roformer_vram_min_mb} MB de VRAM y hay {libre} MB"
    return "roformer", None


def separar_voces(wav: Path, dir_salida: Path, cfg: Config | None = None) -> tuple[Path, Path]:
    """WAV 44.1 kHz → (voz.wav, instrumental.wav) dentro de dir_salida."""
    cfg = cfg or obtener_config()
    separador, motivo = elegir_separador(cfg)
    if motivo:
        log.info("SEPARADOR=auto: se usa Demucs (%s)", motivo)
    if separador == "roformer":
        return separar_con_roformer(wav, dir_salida, cfg)
    if separador != "demucs":
        raise ErrorPipeline(f"SEPARADOR={cfg.separador} no existe (válidos: auto, {', '.join(SEPARADORES)})")
    return separar_con_demucs(wav, dir_salida, cfg)


def comando_roformer(wav: Path, dir_salida: Path, cfg: Config) -> list[str]:
    comando = [str(cfg.ruta(cfg.roformer_python)), str(SCRIPT_ROFORMER), str(Path(wav).resolve()),
               str(Path(dir_salida).resolve()), "--modelo", cfg.roformer_modelo,
               "--dir-modelos", str(cfg.ruta_modelos / "separacion")]
    if cfg.roformer_dereverb:  # MusicAI: además deja voz_seca.wav (referencia sin eco para XTTS y Seed-VC)
        comando += ["--dereverb", cfg.roformer_dereverb]
    return comando


def voz_de_referencia(voz: Path) -> Path:
    """La voz sin reverb si el separador la generó (voz_seca.wav); si no, la voz separada tal cual."""
    seca = Path(voz).with_name("voz_seca.wav")
    return seca if seca.is_file() else Path(voz)


def separar_con_roformer(wav: Path, dir_salida: Path, cfg: Config) -> tuple[Path, Path]:
    if not cfg.ruta(cfg.roformer_python).is_file():
        raise ErrorPipeline(f"SEPARADOR=roformer pero no existe ROFORMER_PYTHON={cfg.roformer_python}")
    dir_salida = Path(dir_salida)
    dir_salida.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(comando_roformer(wav, dir_salida, cfg), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=cfg.roformer_timeout_s)
    except subprocess.TimeoutExpired:
        raise ErrorPipeline(f"RoFormer tardó más de {cfg.roformer_timeout_s} s")
    voz, inst = dir_salida / "voz.wav", dir_salida / "instrumental.wav"
    if r.returncode != 0 or not voz.is_file() or not inst.is_file():
        ultimas = "\n".join((r.stderr or r.stdout).strip().splitlines()[-5:])
        raise ErrorPipeline(f"RoFormer falló (código {r.returncode}): {ultimas}")
    log.info("RoFormer (%s): %s", cfg.roformer_modelo, r.stdout.strip().splitlines()[-1])
    return voz, inst


def separar_con_demucs(wav: Path, dir_salida: Path, cfg: Config) -> tuple[Path, Path]:
    preparar_entorno_modelos(cfg)
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    dir_salida = Path(dir_salida)
    dir_salida.mkdir(parents=True, exist_ok=True)
    audio, sr = sf.read(str(wav), dtype="float32", always_2d=True)  # (muestras, canales)

    dispositivo = cfg.dispositivo if torch.cuda.is_available() else "cpu"
    modelo = get_model(cfg.demucs_modelo)
    modelo.eval()
    try:
        if sr != modelo.samplerate:
            raise ErrorPipeline(f"Demucs espera {modelo.samplerate} Hz y el audio está a {sr} Hz")
        x = torch.from_numpy(audio.T.copy())
        if x.shape[0] == 1:  # mono → estéreo
            x = x.repeat(2, 1)
        # misma normalización que usa la CLI de Demucs
        ref = x.mean(0)
        media, desv = ref.mean(), ref.std() + 1e-8
        x = (x - media) / desv
        # Demucs desplaza el audio un número aleatorio de muestras (shifts=1): sin semilla, cada corrida
        # separa una voz algo distinta y Whisper transcribe otra letra. Se fija solo durante la
        # separación y se devuelve el azar como estaba, para no tocar el de las demás etapas.
        fijar = cfg.demucs_semilla >= 0  # con -1 Demucs sigue con su azar de siempre
        azar = random.getstate()
        if fijar:
            random.seed(cfg.demucs_semilla)
        try:
            with torch.no_grad():
                # split=True procesa por trozos: la VRAM no crece con la duración
                fuentes = apply_model(modelo, x[None], device=dispositivo, split=True,
                                      overlap=0.25, progress=False)[0]
        finally:
            if fijar:
                random.setstate(azar)
        fuentes = fuentes * desv + media
        i_voz = modelo.sources.index("vocals")
        voz = fuentes[i_voz]
        instrumental = fuentes.sum(0) - voz
        ruta_voz, ruta_inst = dir_salida / "voz.wav", dir_salida / "instrumental.wav"
        sf.write(str(ruta_voz), voz.T.cpu().numpy(), sr, subtype="PCM_16")
        sf.write(str(ruta_inst), instrumental.T.cpu().numpy(), sr, subtype="PCM_16")
    finally:
        del modelo
        liberar_vram()
    return ruta_voz, ruta_inst
