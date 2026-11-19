"""Clima musical sugerido, explicable y determinista, sin inferir estados personales."""

from app.modelos import ClimaMusical, RasgosTarareo


def inferir_clima(rasgos: RasgosTarareo) -> ClimaMusical:
    # El modo cuenta, pero no decide solo: una melodía menor rápida puede
    # resultar enérgica. No se usa el volumen del micrófono como emoción.
    tempo = min(1.0, max(0.0, (rasgos.bpm - 60) / 100))
    actividad = min(1.0, rasgos.densidad / 2)
    amplitud = min(1.0, rasgos.rango / 18)
    intensidad = 0.45 * tempo + 0.30 * actividad + 0.15 * amplitud + 0.10 * rasgos.saltos
    menor = rasgos.modo == "menor"
    perfiles = {
        "sereno": (0.20, False, 0.85),
        "melancolico": (0.28, True, 0.85),
        "luminoso": (0.48, False, 0.60),
        "energico": (0.76, None, 0.40),
        "intenso": (0.88, True, 0.70),
    }
    puntajes = {
        nombre: 1 - (0.70 * abs(intensidad - energia)
                     + (0.18 if modo is not None and menor != modo else 0)
                     + 0.12 * abs(rasgos.articulacion - ligado))
        for nombre, (energia, modo, ligado) in perfiles.items()
    }
    orden = sorted(puntajes, key=puntajes.get, reverse=True)
    margen = puntajes[orden[0]] - puntajes[orden[1]]
    etiquetas = {"melancolico": "melancólico", "energico": "enérgico"}
    nombre = orden[0]
    ambiguo = margen < 0.05
    motivo = (f"Clima musical sugerido: {etiquetas.get(nombre, nombre)}; "
              f"{rasgos.bpm:g} BPM, modo {rasgos.modo}, "
              f"{rasgos.densidad:.2f} notas por tiempo y rango de {rasgos.rango} semitonos.")
    if ambiguo:
        motivo += f" También encaja {etiquetas.get(orden[1], orden[1])}."
    return ClimaMusical(nombre=nombre, intensidad=round(intensidad, 4),
                        confianza=round(min(1.0, margen / 0.20), 4),
                        ambiguo=ambiguo, motivo=motivo)
