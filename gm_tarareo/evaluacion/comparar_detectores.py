"""
Compara detectores de melodía con tarareos sintéticos (respuesta conocida) y
con los tarareos reales de tests/audio (sin respuesta: se mide acuerdo y tiempo).

Uso (en Docker, ver evaluacion/README.md):
    python -m evaluacion.comparar_detectores --sinteticos 40 --salida evaluacion/resultados

Métrica principal: F1 de notas de mir_eval (altura ±50 cents, inicio ±100 ms,
sin exigir el final: en un tarareo los finales son difusos). También se
informa la precisión de altura cuadro a cuadro (RPA) y cuántas notas devuelve
cada detector respecto de las reales (el problema medido en limpieza.py:
basic-pitch devolvía ~30 donde había ~15).
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

import mir_eval
import numpy as np
import soundfile as sf

from app.config import obtener_configuracion
from app.pipeline.interpretacion import verificar_alturas
from app.pipeline.limpieza import limpiar_notas
from evaluacion import detectores
from evaluacion.sinteticos import SR, generar

DETECTORES = ('basic_pitch', 'crepe', 'fcpe', 'pyin')
CONFIG = obtener_configuracion()


def _a_arrays(notas):
    if not notas:
        return np.zeros((0, 2)), np.zeros(0)
    intervalos = np.array([[n.inicio, n.fin] for n in notas], dtype=float)
    alturas = np.array([440 * 2 ** ((n.nota - 69) / 12) for n in notas], dtype=float)
    return intervalos, alturas


def _crudas_a_finales(crudas, ruta_wav, nombre):
    """Misma limpieza que producción. A basic-pitch además se le aplica la verificación YIN."""
    confirmadas = set()
    if nombre == 'basic_pitch' and CONFIG.interpretacion_verificar_alturas:
        crudas, confirmadas, _ = verificar_alturas(ruta_wav, crudas)
    finales, _ = limpiar_notas(crudas, CONFIG, confirmadas)
    return [type('N', (), {'nota': n.nota, 'inicio': n.inicio, 'fin': n.inicio + n.duracion})
            for n in finales]


def _detectar(nombre, audio, ruta_wav):
    inicio = time.perf_counter()
    crudas = detectores.basic_pitch(ruta_wav) if nombre == 'basic_pitch' else getattr(detectores, nombre)(audio)
    segundos = time.perf_counter() - inicio
    finales = _crudas_a_finales(crudas, ruta_wav, nombre) if crudas else []
    return crudas, finales, segundos


def _metricas(referencia, estimadas):
    ri, rp = _a_arrays(referencia)
    ei, ep = _a_arrays(estimadas)
    if len(ep) == 0:
        return {'f1': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1_con_final': 0.0}
    p, r, f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ri, rp, ei, ep, onset_tolerance=0.1, pitch_tolerance=50.0, offset_ratio=None)
    _, _, f1_final, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ri, rp, ei, ep, onset_tolerance=0.1, pitch_tolerance=50.0, offset_ratio=0.3)
    return {'f1': f1, 'precision': p, 'recall': r, 'f1_con_final': f1_final}


def _rpa(referencia, estimadas, duracion):
    """Raw pitch accuracy: % de cuadros con voz donde la altura es correcta (±50 cents)."""
    tiempos = np.arange(0, duracion, 0.01)

    def serie(notas):
        hz = np.zeros(len(tiempos))
        for n in notas:
            hz[(tiempos >= n.inicio) & (tiempos < n.fin)] = 440 * 2 ** ((n.nota - 69) / 12)
        return hz

    ref_hz, ref_voz = mir_eval.melody.freq_to_voicing(serie(referencia))
    est_hz, est_voz = mir_eval.melody.freq_to_voicing(serie(estimadas))
    return float(mir_eval.melody.raw_pitch_accuracy(
        ref_voz, mir_eval.melody.hz2cents(ref_hz), est_voz, mir_eval.melody.hz2cents(est_hz)))


def evaluar_sinteticos(cantidad, directorio):
    filas = []
    for tarareo in generar(cantidad):
        ruta = directorio / f'{tarareo.nombre}.wav'
        sf.write(ruta, tarareo.audio, SR)
        duracion = len(tarareo.audio) / SR
        for nombre in DETECTORES:
            crudas, finales, segundos = _detectar(nombre, tarareo.audio, ruta)
            for etapa, notas in (('crudas', crudas), ('limpias', finales)):
                fila = {'tarareo': tarareo.nombre, 'registro': tarareo.registro, 'snr_db': tarareo.snr_db,
                        'detector': nombre, 'etapa': etapa, 'notas_reales': len(tarareo.notas),
                        'notas_detectadas': len(notas), 'segundos': segundos, 'duracion': duracion,
                        **_metricas(tarareo.notas, notas), 'rpa': _rpa(tarareo.notas, notas, duracion)}
                filas.append(fila)
        print(f'{tarareo.nombre} listo', flush=True)
    return filas


def evaluar_reales(carpeta_audio, directorio):
    from app.pipeline.ingesta import ingestar
    from app.pipeline.preprocesado import preprocesar

    filas = []
    for archivo in sorted(Path(carpeta_audio).iterdir()):
        if archivo.suffix.lower() not in {'.wav', '.m4a', '.mp3', '.webm'}:
            continue
        job = directorio / archivo.stem.replace(' ', '_')
        job.mkdir(exist_ok=True)
        try:
            wav, _ = preprocesar(ingestar(archivo, job, SR), job, CONFIG)
        except Exception as exc:  # p. ej. 01 T es demasiado corta: también es un resultado
            filas.append({'tarareo': archivo.name, 'detector': '-', 'error': str(exc)[:80]})
            continue
        audio, _ = sf.read(wav, dtype='float32')
        resultados = {n: _detectar(n, audio, wav) for n in DETECTORES}
        referencia = resultados['basic_pitch'][1]  # producción actual
        for nombre, (crudas, finales, segundos) in resultados.items():
            filas.append({'tarareo': archivo.name, 'detector': nombre, 'notas_crudas': len(crudas),
                          'notas_limpias': len(finales), 'segundos': segundos,
                          'duracion': len(audio) / SR,
                          'acuerdo_con_produccion': _metricas(referencia, finales)['f1']})
        print(f'{archivo.name} listo', flush=True)
    return filas


def resumir(filas):
    resumen = {}
    for nombre in DETECTORES:
        for etapa in ('crudas', 'limpias'):
            sel = [f for f in filas if f['detector'] == nombre and f['etapa'] == etapa]
            if not sel:
                continue
            clave = f'{nombre}/{etapa}'
            resumen[clave] = {
                'f1': float(np.mean([f['f1'] for f in sel])),
                'precision': float(np.mean([f['precision'] for f in sel])),
                'recall': float(np.mean([f['recall'] for f in sel])),
                'f1_con_final': float(np.mean([f['f1_con_final'] for f in sel])),
                'rpa': float(np.mean([f['rpa'] for f in sel])),
                'notas_por_real': float(np.sum([f['notas_detectadas'] for f in sel])
                                        / np.sum([f['notas_reales'] for f in sel])),
                'tiempo_por_segundo_audio': float(np.sum([f['segundos'] for f in sel])
                                                  / np.sum([f['duracion'] for f in sel])),
                'f1_grave': float(np.mean([f['f1'] for f in sel if f['registro'] == 'grave'])),
                'f1_agudo': float(np.mean([f['f1'] for f in sel if f['registro'] == 'agudo'])),
                'f1_ruidoso': float(np.mean([f['f1'] for f in sel if f['snr_db'] < 18] or [0])),
            }
    return resumen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sinteticos', type=int, default=40)
    parser.add_argument('--reales', default='tests/audio')
    parser.add_argument('--salida', default='evaluacion/resultados')
    args = parser.parse_args()

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        sinteticos = evaluar_sinteticos(args.sinteticos, tmp)
        reales = evaluar_reales(args.reales, tmp)

    resultado = {'resumen_sinteticos': resumir(sinteticos), 'sinteticos': sinteticos, 'reales': reales}
    (salida / 'detectores.json').write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(resultado['resumen_sinteticos'], indent=2))


if __name__ == '__main__':
    main()
