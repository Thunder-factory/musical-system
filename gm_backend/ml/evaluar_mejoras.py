"""
Evaluación de "Mejorar con IA" (endpoint generate_from_reference de Modal:
ACE-Step 1.5 en modo cover desde 2026-11-19; antes, audio2audio de ACE-Step v1).

Dos pasos, independientes de Django (solo usa variables de entorno):

1. generar: sube la versión de FluidSynth de cada tarareo a R2 (bajo
   humming/evaluacion/), pide a Modal una mejora por cada estilo × fidelidad,
   EN SERIE (una A100 a la vez, para controlar el costo) y descarga los WAV.
2. medir: calcula por cada resultado
   - estilo (CLAP texto↔audio): similitud con el estilo pedido y su puesto
     frente a los demás estilos del catálogo (1 = el más parecido);
   - fidelidad a la melodía: similitud de croma alineada con DTW contra la
     referencia (0-1; mide notas y armonía, no timbre);
   - variedad (CLAP audio↔audio): distancia media entre estilos del mismo
     tarareo.
   La referencia de FluidSynth también se mide, como línea base.

Uso:
    python -m ml.evaluar_mejoras generar --referencias DIR --salida DIR
    python -m ml.evaluar_mejoras medir --salida DIR
Variables: R2_*, MODAL_KEY, MODAL_SECRET, MODAL_ENDPOINT_FROM_REFERENCE.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from itertools import combinations
from pathlib import Path

import numpy as np

from apps.humming.styles import FIDELITY_STRENGTH, STYLES, STYLES_BY_KEY, build_prompt

ESTILOS_EVALUADOS = ('cumbia', 'rock', 'jazz', 'huayno')
GRILLA = {
    # tarareo de referencia → fidelidades a probar (todas en el primero).
    'mi_tarareo': ('alta', 'media', 'libre'),
    't05': ('media',),
}


# ── 1. Generar ────────────────────────────────────────────────────────────────

def _r2():
    import boto3

    cliente = boto3.client(
        's3', endpoint_url=os.environ['R2_ENDPOINT'], region_name=os.environ.get('R2_REGION', 'auto'),
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
    )
    return cliente, os.environ['R2_DOCUMENTS_BUCKET']


def _modal(body: dict) -> dict:
    import requests

    respuesta = requests.post(
        os.environ['MODAL_ENDPOINT_FROM_REFERENCE'], json=body, timeout=(10, 60),
        headers={'Modal-Key': os.environ['MODAL_KEY'], 'Modal-Secret': os.environ['MODAL_SECRET']},
    )
    respuesta.raise_for_status()
    return respuesta.json()


def generar(referencias: Path, salida: Path, grilla: dict | None = None) -> None:
    """grilla: tarareo → fidelidades (nombre del catálogo o fuerza numérica, p. ej. '0.25')."""
    grilla = grilla or GRILLA
    r2, bucket = _r2()
    salida.mkdir(parents=True, exist_ok=True)
    manifiesto_ruta = salida / 'manifiesto.json'
    manifiesto = json.loads(manifiesto_ruta.read_text(encoding='utf-8')) if manifiesto_ruta.exists() else []
    hechos = {(m['tarareo'], m['estilo'], m['fidelidad']) for m in manifiesto if m.get('archivo')}
    claves_temporales = []

    try:
        for tarareo, fidelidades in grilla.items():
            analisis = json.loads((referencias / tarareo / 'analisis.json').read_text(encoding='utf-8'))
            metadatos = {'bpm': analisis['analisis']['bpm'], 'tonalidad': analisis['analisis']['tonalidad']}
            clave_ref = f'humming/evaluacion/{tarareo}/cancion.mp3'
            r2.upload_file(str(referencias / tarareo / 'cancion.mp3'), bucket, clave_ref)
            claves_temporales.append(clave_ref)
            for fidelidad in fidelidades:
                for estilo in ESTILOS_EVALUADOS:
                    if (tarareo, estilo, fidelidad) in hechos:
                        continue
                    inicio = time.time()
                    envio = _modal({
                        'async': True, 'prompt': build_prompt(STYLES_BY_KEY[estilo].tags, metadatos),
                        'ref_s3_key': clave_ref,
                        'ref_audio_strength': FIDELITY_STRENGTH.get(fidelidad) or float(fidelidad),
                        'audio_duration': analisis['render']['duracionSegundos'], 'infer_step': 60,
                        'seed': 1234, 'instrumental': True,
                    })
                    while True:
                        estado = _modal({'action': 'status', 'remote_job_id': envio['remote_job_id']})
                        if estado['status'] in ('completed', 'failed'):
                            break
                        time.sleep(10)
                    fila = {'tarareo': tarareo, 'estilo': estilo, 'fidelidad': fidelidad,
                            'segundos': round(time.time() - inicio, 1), 'estado': estado['status']}
                    if estado['status'] == 'completed':
                        archivo = f"{tarareo}-{estilo}-{fidelidad}{Path(estado['s3_key']).suffix}"
                        r2.download_file(bucket, estado['s3_key'], str(salida / archivo))
                        for clave in (estado['s3_key'], estado.get('cover_image_s3_key')):
                            if clave:
                                r2.delete_object(Bucket=bucket, Key=clave)
                        fila['archivo'] = archivo
                    else:
                        fila['error'] = estado.get('error_message')
                    manifiesto.append(fila)
                    manifiesto_ruta.write_text(json.dumps(manifiesto, indent=2), encoding='utf-8')
                    print(f"{tarareo} {estilo} {fidelidad}: {fila['estado']} en {fila['segundos']} s", flush=True)
    finally:
        for clave in claves_temporales:
            r2.delete_object(Bucket=bucket, Key=clave)


# ── 2. Medir ──────────────────────────────────────────────────────────────────

SR_CLAP = 48000
SR_CROMA = 22050


def _cargar(ruta: Path, sr: int) -> np.ndarray:
    import librosa

    audio, _ = librosa.load(str(ruta), sr=sr, mono=True)
    return audio


class Clap:
    """CLAP (LAION, laion/clap-htsat-unfused): audio y texto en el mismo espacio."""

    def __init__(self):
        import torch
        from transformers import ClapModel, ClapProcessor

        self.torch = torch
        self.modelo = ClapModel.from_pretrained('laion/clap-htsat-unfused').eval()
        self.procesador = ClapProcessor.from_pretrained('laion/clap-htsat-unfused')

    def texto(self, frases: list[str]) -> np.ndarray:
        entrada = self.procesador(text=frases, return_tensors='pt', padding=True)
        with self.torch.no_grad():
            emb = self.modelo.get_text_features(**entrada)
        return (emb / emb.norm(dim=-1, keepdim=True)).numpy()

    def audio(self, audio: np.ndarray) -> np.ndarray:
        # CLAP ve ~10 s por vez: se promedian ventanas de 10 s a lo largo del tema.
        ventana = 10 * SR_CLAP
        trozos = [audio[i:i + ventana] for i in range(0, max(1, len(audio) - ventana // 2), ventana)]
        entrada = self.procesador(audios=trozos, sampling_rate=SR_CLAP, return_tensors='pt')
        with self.torch.no_grad():
            emb = self.modelo.get_audio_features(**entrada)
        emb = emb / emb.norm(dim=-1, keepdim=True)
        media = emb.mean(dim=0)
        return (media / media.norm()).numpy()


def _fidelidad_croma(referencia: np.ndarray, candidato: np.ndarray) -> float:
    """Similitud media de croma tras alinear con DTW (1 = mismas notas/acordes)."""
    import librosa

    def croma(audio):
        c = librosa.feature.chroma_cqt(y=audio, sr=SR_CROMA, hop_length=2048)
        return c / (np.linalg.norm(c, axis=0, keepdims=True) + 1e-9)

    a, b = croma(referencia), croma(candidato)
    costo, camino = librosa.sequence.dtw(X=a, Y=b, metric='cosine')
    return float(1 - costo[-1, -1] / len(camino))


def medir(referencias: Path, salida: Path) -> dict:
    clap = Clap()
    frases = [f'{s.label} music, {s.tags}' for s in STYLES]
    emb_estilos = clap.texto(frases)
    indice = {s.key: i for i, s in enumerate(STYLES)}

    manifiesto = json.loads((salida / 'manifiesto.json').read_text(encoding='utf-8'))
    resultados, embeddings = [], {}

    def puntuar(ruta: Path, tarareo: str, estilo_pedido: str | None, fidelidad: str):
        audio_clap = _cargar(ruta, SR_CLAP)
        emb = clap.audio(audio_clap)
        similitudes = emb_estilos @ emb
        orden = np.argsort(-similitudes)
        fila = {'tarareo': tarareo, 'estilo': estilo_pedido or 'referencia', 'fidelidad': fidelidad,
                'estilo_top1': STYLES[int(orden[0])].key}
        if estilo_pedido:
            i = indice[estilo_pedido]
            fila['clap_estilo'] = float(similitudes[i])
            fila['puesto_estilo'] = int(np.where(orden == i)[0][0]) + 1
        referencia = _cargar(referencias / tarareo / 'cancion.mp3', SR_CROMA)
        fila['fidelidad_croma'] = _fidelidad_croma(referencia, _cargar(ruta, SR_CROMA))
        return fila, emb

    for tarareo in sorted({m['tarareo'] for m in manifiesto}):
        fila, emb = puntuar(referencias / tarareo / 'cancion.mp3', tarareo, None, '-')
        # Línea base: cuánto "suena" la referencia a cada estilo evaluado.
        for estilo in ESTILOS_EVALUADOS:
            fila[f'clap_{estilo}'] = float(emb_estilos[indice[estilo]] @ emb)
        resultados.append(fila)
        print(f'referencia {tarareo} medida', flush=True)

    for item in manifiesto:
        if not item.get('archivo'):
            continue
        fila, emb = puntuar(salida / item['archivo'], item['tarareo'], item['estilo'], item['fidelidad'])
        fila['segundos_generacion'] = item['segundos']
        resultados.append(fila)
        embeddings[(item['tarareo'], item['estilo'], item['fidelidad'])] = emb
        print(f"{item['archivo']} medido", flush=True)

    variedad = {}
    for (tarareo, fidelidad) in {(t, f) for t, _, f in embeddings}:
        grupo = [e for (t, _, f), e in embeddings.items() if t == tarareo and f == fidelidad]
        if len(grupo) > 1:
            variedad[f'{tarareo}/{fidelidad}'] = float(np.mean([1 - a @ b for a, b in combinations(grupo, 2)]))

    informe = {'resultados': resultados, 'variedad_clap': variedad}
    (salida / 'clap.json').write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding='utf-8')
    return informe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('paso', choices=['generar', 'medir'])
    parser.add_argument('--referencias', type=Path, required=True)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--tarareos', help='Lista separada por comas (por defecto, la grilla fija)')
    parser.add_argument('--fuerzas', help="Fuerzas a probar, p. ej. '0.15,0.25,0.35'")
    args = parser.parse_args()
    grilla = None
    if args.tarareos and args.fuerzas:
        grilla = {t: tuple(args.fuerzas.split(',')) for t in args.tarareos.split(',')}
    if args.paso == 'generar':
        generar(args.referencias, args.salida, grilla)
    else:
        print(json.dumps(medir(args.referencias, args.salida), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
