"""Separa voz e instrumental con un modelo RoFormer (audio-separator) y, opcionalmente, le quita la reverb a la voz.

Corre en un entorno de Python aparte (ROFORMER_PYTHON), NO en el del worker: así las dependencias de
audio-separator no chocan con torch 2.5.1 / coqui-tts del worker, y la VRAM se libera al terminar el proceso.
Basado en el script de SW1; MusicAI añade --dereverb.

Uso:  python separar_roformer.py entrada.wav dir_salida --modelo vocals_mel_band_roformer.ckpt \
          --dir-modelos /models/separacion [--dereverb dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt]
Escribe dir_salida/voz.wav e instrumental.wav; con --dereverb, además voz_seca.wav (la voz sin reverb,
que se usa como referencia de timbre y de melodía). Imprime "OK <segundos>" al final.
"""
import argparse
import logging
import shutil
import sys
import time
from pathlib import Path


def separar(sep, entrada: Path, temporal: Path) -> list[Path]:
    return [temporal / Path(f).name for f in sep.separate(str(entrada))]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("entrada", type=Path)
    p.add_argument("salida", type=Path)
    p.add_argument("--modelo", required=True)
    p.add_argument("--dir-modelos", type=Path, required=True)
    p.add_argument("--dereverb", default="")
    a = p.parse_args()

    from audio_separator.separator import Separator

    inicio = time.perf_counter()
    temporal = a.salida / "_roformer"
    temporal.mkdir(parents=True, exist_ok=True)
    sep = Separator(log_level=logging.WARNING, model_file_dir=str(a.dir_modelos), output_dir=str(temporal),
                    output_format="WAV", sample_rate=44100)
    sep.load_model(model_filename=a.modelo)
    archivos = separar(sep, a.entrada, temporal)
    # cada archivo lleva el nombre del stem entre paréntesis: "(Vocals)", "(Other)" o "(Instrumental)"
    voz = next((f for f in archivos if "(vocals)" in f.name.lower()), None)
    resto = next((f for f in archivos if f is not voz), None)
    if not voz or not resto:
        print(f"ERROR stems inesperados: {[f.name for f in archivos]}", file=sys.stderr)
        return 1
    shutil.move(voz, a.salida / "voz.wav")
    shutil.move(resto, a.salida / "instrumental.wav")

    if a.dereverb:
        sep.load_model(model_filename=a.dereverb)
        secos = separar(sep, a.salida / "voz.wav", temporal)
        # el stem sin reverb se llama "(noreverb)" / "(dry)"; el otro, "(reverb)"
        seca = next((f for f in secos if any(k in f.name.lower() for k in ("noreverb", "no reverb", "dry"))), None)
        if seca is None:
            print(f"AVISO de-reverb sin stem seco reconocible: {[f.name for f in secos]}", file=sys.stderr)
        else:
            shutil.move(seca, a.salida / "voz_seca.wav")

    shutil.rmtree(temporal, ignore_errors=True)
    import torch
    print(f"OK {time.perf_counter() - inicio:.1f} cuda={torch.cuda.is_available()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
