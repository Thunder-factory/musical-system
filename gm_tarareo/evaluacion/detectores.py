"""
Detectores de melodía a comparar, todos con la misma salida: list[NotaCruda].

- basic-pitch (actual): CNN audio→notas de Spotify (Apache 2.0).
- CREPE (torchcrepe, MIT): CNN de f0 monofónica, muy precisa en voz.
- FCPE (torchfcpe, MIT): estimador de f0 rápido usado en conversión de voz
  (familia de RMVPE, empaquetado en pip y con licencia clara).
- pYIN (librosa, ISC): método clásico probabilístico, sin red neuronal.

Los tres últimos dan una curva de f0 (no notas), así que se segmenta igual
para todos con `segmentar`: así la comparación mide el estimador, no el
segmentador. Las notas pasan después por la misma limpieza del worker.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter

from app.pipeline.melodia import NotaCruda

SR = 22050
SALTO_S = 0.01  # 10 ms por cuadro
FMIN, FMAX = 65.0, 1000.0  # C2 a B5: cubre voces graves y agudas


def segmentar(f0_hz: np.ndarray, confianza: np.ndarray, *, umbral: float,
              salto_s: float = SALTO_S, minimo_s: float = 0.06) -> list[NotaCruda]:
    """
    Curva de f0 → notas. Una nota nueva empieza cuando el pitch se aleja más
    de 0.6 semitonos del centro de la nota actual durante 3 cuadros seguidos
    (así el vibrato y la desafinación no la parten, pero un cambio real sí).
    """
    sonora = (confianza >= umbral) & (f0_hz > 0)
    midi = np.where(sonora, 69 + 12 * np.log2(np.maximum(f0_hz, 1e-6) / 440), np.nan)
    suave = midi.copy()
    validos = ~np.isnan(midi)
    if validos.any():
        suave[validos] = median_filter(midi[validos], size=5, mode='nearest')

    notas: list[NotaCruda] = []
    inicio, valores, confs, fuera = None, [], [], 0

    def cerrar(fin_idx: int):
        if inicio is not None and len(valores) >= 1 and (fin_idx - inicio) * salto_s >= minimo_s:
            notas.append(NotaCruda(
                nota=int(round(float(np.median(valores)))),
                inicio=round(inicio * salto_s, 4),
                fin=round(fin_idx * salto_s, 4),
                amplitud=float(np.clip(np.mean(confs), 0, 1)),
            ))

    for i, valor in enumerate(suave):
        if np.isnan(valor):
            cerrar(i)
            inicio, valores, confs, fuera = None, [], [], 0
            continue
        if inicio is None:
            inicio, valores, confs, fuera = i, [valor], [confianza[i]], 0
            continue
        centro = float(np.median(valores[-15:]))
        if abs(valor - centro) > 0.6:
            fuera += 1
            if fuera >= 3:
                corte = i - 2
                cerrar(corte)
                inicio, valores, confs, fuera = corte, list(suave[corte:i + 1]), list(confianza[corte:i + 1]), 0
                continue
        else:
            fuera = 0
        valores.append(valor)
        confs.append(confianza[i])
    cerrar(len(suave))
    return notas


def basic_pitch(ruta_wav) -> list[NotaCruda]:
    from app.pipeline.melodia import extraer_notas_crudas

    return extraer_notas_crudas(ruta_wav)


def crepe(audio: np.ndarray) -> list[NotaCruda]:
    import librosa
    import torch
    import torchcrepe

    # CREPE trabaja a 16 kHz: 160 muestras de salto = 10 ms, igual que el resto.
    x16 = torch.tensor(librosa.resample(audio, orig_sr=SR, target_sr=16000), dtype=torch.float32)[None]
    f0, periodicidad = torchcrepe.predict(
        x16, 16000, hop_length=160, fmin=FMIN, fmax=FMAX, model='full',
        decoder=torchcrepe.decode.viterbi, return_periodicity=True, batch_size=512, device='cpu',
    )
    periodicidad = torchcrepe.filter.median(periodicidad, 3)
    return segmentar(f0[0].numpy(), periodicidad[0].numpy(), umbral=0.5)


_fcpe = None


def fcpe(audio: np.ndarray) -> list[NotaCruda]:
    import torch
    from torchfcpe import spawn_bundled_infer_model

    global _fcpe
    if _fcpe is None:
        _fcpe = spawn_bundled_infer_model(device='cpu')
    x = torch.tensor(audio, dtype=torch.float32)[None, :, None]
    cuadros = int(len(audio) / (SR * SALTO_S)) + 1
    f0 = _fcpe.infer(x, sr=SR, decoder_mode='local_argmax', threshold=0.006,
                     f0_min=FMIN, f0_max=FMAX, interp_uv=False, output_interp_target_length=cuadros)
    f0 = f0.squeeze().numpy()
    # FCPE marca los cuadros sin voz con f0 = 0: la confianza es binaria.
    return segmentar(f0, (f0 > 0).astype(float), umbral=0.5)


def pyin(audio: np.ndarray) -> list[NotaCruda]:
    import librosa

    f0, sonoro, prob = librosa.pyin(audio, fmin=FMIN, fmax=FMAX, sr=SR,
                                    frame_length=2048, hop_length=int(SR * SALTO_S))
    return segmentar(np.nan_to_num(f0), np.where(sonoro, prob, 0.0), umbral=0.3)
