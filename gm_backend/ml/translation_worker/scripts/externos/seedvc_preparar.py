"""Descarga una sola vez los modelos que usa Seed-VC en modo canto (los mismos que seedvc_cantar.py).

Se ejecuta con cwd = carpeta de Seed-VC y CON conexión (al cantar, el worker usa HF_HUB_OFFLINE=1):
  - ./checkpoints: Plachta/Seed-VC (DiT de canto 44 kHz + config) y funasr/campplus.
  - caché de Hugging Face (HF_HUB_CACHE): BigVGAN 44 kHz y openai/whisper-small.
  - RMVPE (extractor de melodía) en la ruta que recibe seedvc_cantar.py con --rmvpe.

Uso:  python seedvc_preparar.py --rmvpe /models/applio/rvc/models/predictors/rmvpe.pt
"""
import argparse
import os
import shutil
import sys
import types
from pathlib import Path


def _sin_dac() -> None:
    """Igual que seedvc_cantar.py: el modelo de canto no usa dac."""
    for nombre in ("dac", "dac.nn", "dac.nn.quantize"):
        sys.modules[nombre] = types.ModuleType(nombre)
    sys.modules["dac.nn.quantize"].VectorQuantize = object


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rmvpe", required=True)
    a = p.parse_args()

    _sin_dac()
    sys.path.insert(0, os.getcwd())
    import huggingface_hub  # antes que inference.py, para fijar HF_HUB_CACHE (ver seedvc_cantar.py)
    import transformers  # noqa: F401

    destino = Path(a.rmvpe)
    if not destino.is_file():
        destino.parent.mkdir(parents=True, exist_ok=True)
        descargado = huggingface_hub.hf_hub_download("lj1995/VoiceConversionWebUI", "rmvpe.pt")
        shutil.copyfile(descargado, destino)
    print(f"RMVPE: listo en {destino}")

    import inference as sv  # Seed-VC

    real = sv.load_custom_model_from_hf

    def cargar(repo_id, model_filename="pytorch_model.bin", config_filename=None):
        if repo_id == "lj1995/VoiceConversionWebUI" and model_filename == "rmvpe.pt":
            return str(destino)
        return real(repo_id, model_filename, config_filename)
    sv.load_custom_model_from_hf = cargar

    sv.load_models(argparse.Namespace(f0_condition=True, checkpoint=None, config=None, fp16=True))
    print("Seed-VC (canto 44 kHz): modelos listos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
