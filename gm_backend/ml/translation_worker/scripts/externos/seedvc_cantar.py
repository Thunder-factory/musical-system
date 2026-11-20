"""Convierte la voz sintetizada a la voz del cantante original y le pone SU melodía (Seed-VC, modo canto).

Se ejecuta como proceso aparte con el Python del worker y con cwd = carpeta de Seed-VC (SEEDVC_DIR), para que
la VRAM se libere al terminar. Basado en inference.py de Seed-VC (GPL-3.0, github.com/Plachtaa/seed-vc),
con un cambio: la curva de tono (F0) que guía la conversión no sale de la voz sintetizada (que es habla)
sino de la voz original separada, en los mismos instantes (las dos pistas están alineadas en el tiempo).

Uso:  python seedvc_cantar.py --fuente voz_nueva.wav --original voz_original.wav --referencia ref.wav \
          --salida voz_cantada.wav --rmvpe ruta/rmvpe.pt [--melodia original|fuente] [--pasos 30] [--cfg 0.7]
Imprime "OK <segundos> <frames_con_melodia_original>/<frames_con_voz>" al terminar.
"""
import argparse
import os
import sys
import time
import types

import numpy as np


def _sin_dac() -> None:
    """Seed-VC importa dac solo para una opción (vector_quantize) que el modelo de canto no usa;
    instalar dac bajaría protobuf y rompería otras partes del worker."""
    if "dac" in sys.modules:
        return
    class VectorQuantize:  # noqa: D401
        def __init__(self, *a, **k):
            raise RuntimeError("vector_quantize no está soportado en este entorno")
    for nombre in ("dac", "dac.nn", "dac.nn.quantize"):
        sys.modules[nombre] = types.ModuleType(nombre)
    sys.modules["dac.nn.quantize"].VectorQuantize = VectorQuantize


def _a_semitonos(f0: np.ndarray) -> np.ndarray:
    return 12.0 * np.log2(np.maximum(f0, 1e-5) / 440.0) + 69.0


def _a_hz(semitonos: np.ndarray) -> np.ndarray:
    return 440.0 * 2.0 ** ((semitonos - 69.0) / 12.0)


def limpiar_melodia(f0: np.ndarray, f0_original: np.ndarray, ventana_octava: int = 50,
                    mediana: int = 5, margen_rango: float = 2.0) -> tuple[np.ndarray, int]:
    """MusicAI: quita de la curva de tono lo que Seed-VC convierte en «gallos».

    1. Saltos de octava: el detector (RMVPE) a veces lee la nota una octava arriba o abajo, sobre todo con
       restos del instrumental. Si un cuadro se aleja ~12 semitonos de la mediana de su entorno (0.5 s),
       se lleva a la octava correcta.
    2. Rango vocal: cada nota se limita al rango real del cantante (percentiles 2-98 de su voz ± 2 st).
    3. Picos sueltos: filtro de mediana de 5 cuadros (50 ms) dentro de cada tramo con voz; los cambios de
       nota reales duran más y se conservan.
    Devuelve (f0 limpio, cuadros corregidos). Los cuadros sordos (0) no se tocan.
    """
    salida = np.asarray(f0, dtype=np.float64).copy()
    voz = salida > 1
    original = np.asarray(f0_original, dtype=np.float64)
    if voz.sum() < 3 or (original > 1).sum() < 3:
        return salida, 0
    st = _a_semitonos(salida)
    antes = st.copy()

    # 1) octava: comparar con la mediana local de los cuadros con voz
    idx = np.flatnonzero(voz)
    for k in idx:
        vecinos = idx[(idx >= k - ventana_octava) & (idx <= k + ventana_octava)]
        ref = np.median(st[vecinos])
        dif = st[k] - ref
        if abs(dif) > 8.5:
            st[k] -= 12.0 * np.round(dif / 12.0)

    # 2) rango vocal del cantante
    orig_st = _a_semitonos(original[original > 1])
    bajo, alto = np.percentile(orig_st, 2) - margen_rango, np.percentile(orig_st, 98) + margen_rango
    centro = (bajo + alto) / 2.0
    fuera = voz & ((st < bajo) | (st > alto))
    # primero se mueve por octavas completas hacia el centro del rango (no aplana la melodía)...
    st[fuera] -= 12.0 * np.round((st[fuera] - centro) / 12.0)
    # ...y solo lo que siga fuera se recorta al borde
    st[voz] = np.clip(st[voz], bajo, alto)

    # 3) mediana por tramos con voz
    mitad = mediana // 2
    inicio = None
    for k in range(len(st) + 1):
        sonando = k < len(st) and voz[k]
        if sonando and inicio is None:
            inicio = k
        elif not sonando and inicio is not None:
            tramo = st[inicio:k].copy()
            if len(tramo) >= mediana:
                for j in range(len(tramo)):
                    st[inicio + j] = np.median(tramo[max(0, j - mitad): j + mitad + 1])
            inicio = None

    corregidos = int((np.abs(st - antes) > 0.5)[voz].sum())
    salida[voz] = _a_hz(st[voz])
    return salida, corregidos


def melodia_alineada(f0_fuente: np.ndarray, f0_original: np.ndarray, vecindad: int = 15) -> tuple[np.ndarray, int]:
    """F0 por cuadro para la conversión: donde la voz nueva suena, la nota del original en ese instante.

    Si en ese cuadro el original no canta (la frase traducida es más larga, por ejemplo), se usa la nota
    original más cercana dentro de `vecindad` cuadros (0.3 s); si tampoco hay, la de la voz nueva llevada
    a la altura media del original. Donde la voz nueva no suena, 0 (sordo).
    """
    n = len(f0_fuente)
    orig = np.zeros(n)
    m = min(n, len(f0_original))
    orig[:m] = f0_original[:m]
    con_voz_o = np.flatnonzero(orig > 1)
    salida = np.zeros(n)
    usados = 0
    if con_voz_o.size == 0:
        return f0_fuente.copy(), 0
    ajuste = np.median(np.log(orig[orig > 1])) - np.median(np.log(f0_fuente[f0_fuente > 1] + 1e-5)) \
        if (f0_fuente > 1).any() else 0.0
    for k in np.flatnonzero(f0_fuente > 1):
        if orig[k] > 1:
            salida[k] = orig[k]
            usados += 1
            continue
        j = con_voz_o[np.argmin(np.abs(con_voz_o - k))]
        if abs(j - k) <= vecindad:
            salida[k] = orig[j]
            usados += 1
        else:
            salida[k] = np.exp(np.log(f0_fuente[k]) + ajuste)
    return salida, usados


def elegir_corte(energia: np.ndarray, hechos: int, ventana: int, solape: int, desde: float = 0.6) -> int:
    """MusicAI: largo del trozo que empieza en `hechos` para que termine en el tramo más silencioso.

    Seed-VC convierte la canción por trozos (su contexto es de 30 s, menos la referencia) y los une con un
    fundido corto. Con un corte fijo, la unión cae en mitad de una nota y se oye un salto de timbre o de
    volumen. Aquí se busca, entre el 60 % y el 100 % de la ventana, el punto donde la energía de la voz
    (media en `solape` cuadros, lo que dura el fundido) es mínima. Devuelve el largo en cuadros.
    """
    total = len(energia)
    if hechos + ventana >= total:
        return total - hechos  # último trozo: hasta el final
    a, b = hechos + int(ventana * desde), hechos + ventana
    if b - a <= solape:
        return ventana
    media = np.convolve(energia[a - solape: b], np.ones(solape) / solape, mode="valid")  # media terminada en cada cuadro
    fin = a + int(np.argmin(media[-(b - a):]))
    return max(solape * 2, fin - hechos + 1)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fuente", required=True)
    p.add_argument("--original", required=True)
    p.add_argument("--referencia", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--rmvpe", required=True)
    p.add_argument("--melodia", choices=["original", "fuente"], default="original")
    p.add_argument("--pasos", type=int, default=30)
    p.add_argument("--cfg", type=float, default=0.7)
    p.add_argument("--semitonos", type=int, default=0)
    p.add_argument("--limpiar", action="store_true", help="limpiar la melodía (octavas, rango, picos)")
    a = p.parse_args()

    _sin_dac()
    sys.path.insert(0, os.getcwd())
    # inference.py cambia HF_HUB_CACHE al importarse; huggingface_hub lee esa ruta una sola vez, al importarse
    # él. Importándolo antes, Whisper-small y BigVGAN se buscan en la caché del proyecto (HF_HOME del worker)
    # y no se descargan de nuevo. HF_HUB_OFFLINE=1 (lo pone el worker) evita cualquier descarga.
    import huggingface_hub  # noqa: F401
    import transformers  # noqa: F401
    import librosa
    import soundfile as sf
    import torch
    import torchaudio

    import inference as sv  # Seed-VC

    real = sv.load_custom_model_from_hf

    def cargar(repo_id, model_filename="pytorch_model.bin", config_filename=None):  # misma firma que hf_utils
        if repo_id == "lj1995/VoiceConversionWebUI" and model_filename == "rmvpe.pt":
            return a.rmvpe  # el de Applio: no se descarga otra copia
        return real(repo_id, model_filename, config_filename)
    sv.load_custom_model_from_hf = cargar

    inicio = time.perf_counter()
    args = argparse.Namespace(f0_condition=True, checkpoint=None, config=None, fp16=True)
    model, semantic_fn, f0_fn, vocoder_fn, campplus_model, mel_fn, mel_fn_args = sv.load_models(args)
    device = sv.device
    sr, hop = 44100, 512
    max_context_window = sr // hop * 30
    overlap_frame_len = 16
    overlap_wave_len = overlap_frame_len * hop

    with torch.no_grad():
        fuente = torch.tensor(librosa.load(a.fuente, sr=sr)[0]).unsqueeze(0).float().to(device)
        ref = torch.tensor(librosa.load(a.referencia, sr=sr)[0][: sr * 25]).unsqueeze(0).float().to(device)
        original = librosa.load(a.original, sr=16000)[0]

        f16 = torchaudio.functional.resample(fuente, sr, 16000)
        if f16.size(-1) <= 16000 * 30:
            S_alt = semantic_fn(f16)
        else:  # igual que inference.py: trozos de 30 s con 5 s de solape
            trozos, buffer, recorrido = [], None, 0
            while recorrido < f16.size(-1):
                if buffer is None:
                    trozo = f16[:, recorrido:recorrido + 16000 * 30]
                else:
                    trozo = torch.cat([buffer, f16[:, recorrido:recorrido + 16000 * 25]], dim=-1)
                S = semantic_fn(trozo)
                trozos.append(S if recorrido == 0 else S[:, 50 * 5:])
                buffer = trozo[:, -16000 * 5:]
                recorrido += 30 * 16000 if recorrido == 0 else trozo.size(-1) - 16000 * 5
            S_alt = torch.cat(trozos, dim=1)
        r16 = torchaudio.functional.resample(ref, sr, 16000)
        S_ori = semantic_fn(r16)
        mel, mel2 = mel_fn(fuente), mel_fn(ref)
        target_lengths = torch.LongTensor([mel.size(2)]).to(device)
        target2_lengths = torch.LongTensor([mel2.size(2)]).to(device)
        feat2 = torchaudio.compliance.kaldi.fbank(r16, num_mel_bins=80, dither=0, sample_frequency=16000)
        style2 = campplus_model((feat2 - feat2.mean(dim=0, keepdim=True)).unsqueeze(0))

        F0_ref = torch.from_numpy(f0_fn(r16[0], thred=0.03)).to(device)[None]
        f0_fuente = f0_fn(f16[0], thred=0.03)
        f0_orig = f0_fn(torch.from_numpy(original).to(device), thred=0.03)
        if a.melodia == "original":
            f0_guia, usados = melodia_alineada(np.asarray(f0_fuente), np.asarray(f0_orig))
        else:
            f0_guia, usados = np.asarray(f0_fuente), 0
        corregidos = 0
        if a.limpiar:  # MusicAI: sin saltos de octava, dentro del rango del cantante y sin picos
            f0_guia, corregidos = limpiar_melodia(f0_guia, np.asarray(f0_orig))
        con_voz = int((np.asarray(f0_fuente) > 1).sum())
        f0_guia = torch.from_numpy(f0_guia).float().to(device)[None]
        if a.semitonos:
            f0_guia[f0_guia > 1] = sv.adjust_f0_semitones(f0_guia[f0_guia > 1], a.semitonos)

        cond = model.length_regulator(S_alt, ylens=target_lengths, n_quantizers=3, f0=f0_guia)[0]
        prompt = model.length_regulator(S_ori, ylens=target2_lengths, n_quantizers=3, f0=F0_ref)[0]

        ventana = max_context_window - mel2.size(2)
        # MusicAI: energía de la voz por cuadro (mismo eje que cond) para cortar los trozos en silencios
        energia = mel[0].float().mean(0).cpu().numpy()
        if len(energia) != cond.size(1):
            energia = np.resize(energia, cond.size(1))
        cortes = []
        hechos, partes, previo = 0, [], None
        while hechos < cond.size(1):
            largo = elegir_corte(energia, hechos, ventana, overlap_frame_len)
            trozo = cond[:, hechos:hechos + largo]
            ultimo = hechos + largo >= cond.size(1)
            if not ultimo:
                cortes.append(round((hechos + largo) * hop / sr, 2))
            cat = torch.cat([prompt, trozo], dim=1)
            with torch.autocast(device_type=device.type, dtype=torch.float16):
                vc = model.cfm.inference(cat, torch.LongTensor([cat.size(1)]).to(device), mel2, style2, None,
                                         a.pasos, inference_cfg_rate=a.cfg)[:, :, mel2.size(-1):]
            onda = vocoder_fn(vc.float()).squeeze()[None, :]
            if previo is None:
                if ultimo:
                    partes.append(onda[0].cpu().numpy())
                    break
                partes.append(onda[0, :-overlap_wave_len].cpu().numpy())
            elif ultimo:
                partes.append(sv.crossfade(previo.cpu().numpy(), onda[0].cpu().numpy(), overlap_wave_len))
                break
            else:
                partes.append(sv.crossfade(previo.cpu().numpy(), onda[0, :-overlap_wave_len].cpu().numpy(),
                                           overlap_wave_len))
            previo = onda[0, -overlap_wave_len:]
            hechos += vc.size(2) - overlap_frame_len
        salida = np.concatenate(partes)
    n = fuente.size(-1)  # misma duración que la entrada: la mezcla espera las pistas alineadas
    salida = np.pad(salida, (0, max(0, n - len(salida))))[:n]
    sf.write(a.salida, salida, sr, subtype="PCM_16")
    print(f"OK {time.perf_counter() - inicio:.1f} {usados}/{con_voz}", file=sys.stdout)
    print(f"MELODIA corregidos={corregidos}", file=sys.stderr)
    print(f"TROZOS ventana={ventana * hop / sr:.1f}s uniones={cortes}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
