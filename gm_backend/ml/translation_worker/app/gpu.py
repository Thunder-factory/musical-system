"""Utilidades de GPU: leer VRAM, liberar modelos y medir cada etapa.

La VRAM se lee con NVML (global de la tarjeta), así también cuenta lo que usan
ctranslate2 (faster-whisper) y Ollama, que torch no ve.
"""
import gc
import logging
import threading
import time
from contextlib import contextmanager

log = logging.getLogger("worker.gpu")


def _nvml():
    """Devuelve (pynvml, handle) o None si no hay GPU NVIDIA disponible."""
    try:
        import pynvml

        pynvml.nvmlInit()
        return pynvml, pynvml.nvmlDeviceGetHandleByIndex(0)
    except Exception:
        return None


def info_gpu() -> dict:
    """Nombre de la GPU y VRAM total / usada / libre en MB."""
    n = _nvml()
    if n is None:
        return {"gpu": None, "vram_total_mb": 0, "vram_usada_mb": 0, "vram_libre_mb": 0}
    pynvml, h = n
    nombre = pynvml.nvmlDeviceGetName(h)
    if isinstance(nombre, bytes):
        nombre = nombre.decode()
    mem = pynvml.nvmlDeviceGetMemoryInfo(h)
    mb = 1024 * 1024
    return {
        "gpu": nombre.replace("NVIDIA GeForce ", ""),
        "vram_total_mb": mem.total // mb,
        "vram_usada_mb": mem.used // mb,
        "vram_libre_mb": mem.free // mb,
    }


def vram_usada_mb() -> int:
    return info_gpu()["vram_usada_mb"]


def liberar_vram() -> None:
    """Llamar después de `del modelo` para devolver la memoria a la GPU."""
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except ImportError:
        pass


@contextmanager
def medir_etapa(nombre: str, limite_mb: int = 7700, intervalo_s: float = 0.25):
    """Registra duración y pico de VRAM (global) de una etapa del pipeline.

    Uso:  with medir_etapa("separando") as m: ...   →  m["segundos"], m["vram_pico_mb"]
    """
    medida = {"etapa": nombre, "segundos": 0.0, "vram_inicio_mb": vram_usada_mb(), "vram_pico_mb": 0}
    medida["vram_pico_mb"] = medida["vram_inicio_mb"]
    parar = threading.Event()

    def muestrear():
        while not parar.wait(intervalo_s):
            medida["vram_pico_mb"] = max(medida["vram_pico_mb"], vram_usada_mb())

    hilo = threading.Thread(target=muestrear, daemon=True)
    inicio = time.perf_counter()
    hilo.start()
    try:
        yield medida
    finally:
        parar.set()
        hilo.join()
        medida["vram_pico_mb"] = max(medida["vram_pico_mb"], vram_usada_mb())
        medida["segundos"] = round(time.perf_counter() - inicio, 2)
        log.info(
            "etapa=%s tiempo=%.1fs vram_pico=%dMB (inicio=%dMB)",
            nombre, medida["segundos"], medida["vram_pico_mb"], medida["vram_inicio_mb"],
        )
        if medida["vram_pico_mb"] > limite_mb:
            log.warning("etapa=%s superó el límite de VRAM: %dMB > %dMB",
                        nombre, medida["vram_pico_mb"], limite_mb)
