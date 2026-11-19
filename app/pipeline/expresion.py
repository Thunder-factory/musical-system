"""Conserva el contorno cantado, centrado en la nota afinada y limitado a 35 cents."""

from dataclasses import replace

import numpy as np

from app.modelos import PuntoExpresion
from app.pipeline.arreglo import ResultadoArreglo

# El bend se reserva para instrumentos sostenidos: no deslizar un piano ni la batería.
PROGRAMAS_EXPRESIVOS = frozenset(range(40, 45)) | frozenset(range(48, 104))


def conservar_expresion(limpias, crudas, intensidad: float = 1.0) -> None:
    """Alinea los contornos crudos con las notas finales (también si se fusionaron)."""
    for nota in limpias:
        tiempos, valores = [], []
        for cruda in crudas:
            if cruda.nota != nota.nota or not cruda.pitch_bends:
                continue
            for t, valor in zip(np.linspace(cruda.inicio, cruda.fin, len(cruda.pitch_bends), endpoint=False),
                                cruda.pitch_bends, strict=True):
                if nota.inicio <= t < nota.inicio + nota.duracion:
                    tiempos.append((t - nota.inicio) / nota.duracion)
                    valores.append(valor)
        if len(valores) < 3:
            continue
        orden = np.argsort(tiempos)
        posiciones = np.asarray(tiempos)[orden]
        v = np.asarray(valores)[orden]
        v = np.convolve(np.pad(v, (1, 1), mode="edge"), np.ones(3) / 3, mode="valid")
        # El desafinado constante no se copia: solo la variación expresiva.
        v = np.clip(v - np.median(v), -0.35, 0.35) * intensidad
        indices = np.unique(np.linspace(0, len(v) - 1, min(32, len(v)), dtype=int))
        nota.expresion = [PuntoExpresion(posicion=0, semitonos=0)] + [
            PuntoExpresion(posicion=round(float(posiciones[i]), 5), semitonos=round(float(v[i]), 4))
            for i in indices if 0 < posiciones[i] < 1
        ] + [PuntoExpresion(posicion=1, semitonos=0)]


def expresar_arreglo(resultado: ResultadoArreglo, analisis, armonia) -> ResultadoArreglo:
    programa = next(p.programa for p in resultado.arreglo.pistas if p.rol == "melodia")
    if programa not in PROGRAMAS_EXPRESIVOS:
        return resultado
    corrimiento = armonia.anacrusaPulsos - (4 if armonia.anacrusaPulsos else 0)
    posiciones = []
    for s in resultado.arreglo.estructura:
        if s.nombre not in ("A", "A'", "A final"):
            continue
        for n in analisis.melodiaCuantizada:
            posiciones.append((s.compasInicio * 4 + n.inicioPulsos + corrimiento, n))
    eventos = []
    for e in resultado.eventos:
        curva = ()
        if e.pista == "melodia":
            if e.origenPulsos is not None:
                n = next((n for n in analisis.melodiaCuantizada
                          if abs(n.inicioPulsos-e.origenPulsos) < 0.001 and n.nota % 12 == e.nota % 12), None)
            else:
                n = next((n for t, n in posiciones if abs(t - e.inicio) < 0.001 and n.nota % 12 == e.nota % 12), None)
            if n is not None:
                curva = tuple((p.posicion, p.semitonos) for p in n.expresion)
        eventos.append(replace(e, expresion=curva))
    return ResultadoArreglo(resultado.arreglo, eventos)
