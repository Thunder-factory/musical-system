"""Selecciona una frase como gancho. Distingue repetición observada de propuesta."""

import math

import numpy as np

from app.modelos import GanchoMusical


def detectar_gancho(notas) -> GanchoMusical:
    ordenadas = sorted(notas, key=lambda n: n.inicioPulsos)
    mejor = None
    for largo in range(3, min(8, len(ordenadas) // 2) + 1):
        for i in range(len(ordenadas) - 2 * largo + 1):
            a = ordenadas[i:i+largo]
            intervalos = np.diff([n.nota for n in a])
            ritmos = np.diff([n.inicioPulsos for n in a])
            ritmos = ritmos / max(float(np.median(ritmos)), 0.01)
            for j in range(i+largo, len(ordenadas) - largo + 1):
                b = ordenadas[j:j+largo]
                # Una nota repetida sola no es evidencia de un motivo musical.
                if len({n.nota for n in a}) < 2:
                    continue
                alturas = float(np.mean(intervalos == np.diff([n.nota for n in b])))
                rb = np.diff([n.inicioPulsos for n in b])
                rb = rb / max(float(np.median(rb)), 0.01)
                ritmo = float(np.mean(np.abs(ritmos-rb) <= 0.35))
                similitud = 0.75 * alturas + 0.25 * ritmo
                if alturas >= 0.85 and similitud >= 0.85:
                    candidato = (largo * similitud, similitud, -i, i, largo)
                    if mejor is None or candidato > mejor:
                        mejor = candidato
    if mejor:
        _, confianza, _, inicio, largo = mejor
        frase = ordenadas[inicio:inicio+largo]
        motivo = "Frase repetida: intervalos y ritmo similares, aunque cambie la altura de partida."
    else:
        # Buscar una frase real delimitada por pausas, no asignar certeza ficticia.
        frases, frase = [], []
        for n in ordenadas:
            if frase and n.inicioPulsos - (frase[-1].inicioPulsos + frase[-1].duracionPulsos) >= 0.75:
                frases.append(frase)
                frase = []
            frase.append(n)
        if frase:
            frases.append(frase)
        frase = max(frases, key=lambda f: (min(len(f), 8), f[-1].duracionPulsos))[:8]
        confianza = 0.0
        motivo = "Propuesta de composición: no se encontró una repetición clara; se eligió una frase representativa."
    inicio = math.floor(frase[0].inicioPulsos / 4) * 4
    fin = math.ceil((frase[-1].inicioPulsos + frase[-1].duracionPulsos) / 4) * 4
    return GanchoMusical(inicioPulsos=inicio, duracionPulsos=max(4, fin-inicio), notas=len(frase),
                         repetido=mejor is not None, confianza=round(confianza, 3), motivo=motivo)
