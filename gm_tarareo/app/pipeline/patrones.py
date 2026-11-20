"""Tres familias rítmicas por estilo, deterministas y con identidad propia."""

from dataclasses import replace


def adaptar_acompanamiento(patron, familia):
    if familia == "aire":
        return tuple((p, d, str(2-int(q) % 3) if q.isdigit() else q)
                     for i, (p, d, q) in enumerate(patron) if i % 2 == 0)
    if familia == "impulso" and not any(p == 3.5 for p, _, _ in patron):
        return patron + ((3.5, 0.35, "quinta" if any(q == "quinta" for _, _, q in patron) else "acorde"),)
    return patron


def variar_patrones(estilo, huella):
    indice = (huella // 13) % 3
    if indice == 0:
        return estilo, "base"
    # La transformación actúa dentro de la familia del estilo: no convierte
    # el pulso electrónico en rock ni agrega batería completa al folk.
    bateria = {n: tuple(p) for n, p in estilo.bateria.items()}
    if indice == 1:
        # Aire: hi-hat/shaker en negras, síncopa de bajo y arpegio descendente.
        for n in (42, 46, 70):
            if n in bateria:
                bateria[n] = tuple(p for k, p in enumerate(bateria[n]) if k % 2 == 0)
        bajo = tuple((p, d, intervalo) for k, (p, d, intervalo) in enumerate(estilo.bajo) if k % 2 == 0)
        return replace(estilo, bateria=bateria, bajo=bajo or estilo.bajo), "aire"
    # Impulso: refuerzo de bombo/timbal al final del tercer tiempo y bajo
    # algo más corto. La caja/palmas en 2 y 4 se mantiene.
    for n in (36, 45, 54):
        if n in bateria:
            bateria[n] = tuple(sorted(set(bateria[n]) | {2.5}))
    bajo = tuple((p, min(d, 0.75), intervalo) for p, d, intervalo in estilo.bajo)
    return replace(estilo, bateria=bateria, bajo=bajo), "impulso"
