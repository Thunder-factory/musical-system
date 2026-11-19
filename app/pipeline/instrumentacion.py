"""Capas de color por estilo, con espacio para la melodía y la segunda voz."""

from dataclasses import dataclass, replace

from app.modelos import PistaArreglo


@dataclass(frozen=True)
class Color:
    nombre: str
    programa: int
    patron: str


# General MIDI, programas desde cero. Cada estilo mantiene su identidad.
COLORES = {
    "balada": (Color("Cuerdas suaves", 48, "sostenido"), Color("Guitarra acústica", 24, "arpegio")),
    "pop": (Color("Guitarra limpia", 27, "pulsos"), Color("Detalle de sintetizador", 88, "detalle")),
    "rock_suave": (Color("Órgano", 16, "sostenido"), Color("Guitarra limpia de apoyo", 27, "pulsos")),
    "lofi": (Color("Guitarra jazz", 26, "pulsos"), Color("Vibráfono", 11, "detalle")),
    "folk": (Color("Violín", 40, "sostenido"), Color("Flauta", 73, "detalle")),
    "epico": (Color("Trompas", 60, "sostenido"), Color("Coro instrumental", 52, "sostenido")),
    "electronico": (Color("Arpegio de sintetizador", 81, "arpegio"), Color("Pad atmosférico", 89, "sostenido")),
}


def ampliar_instrumentacion(preset, variante, acordes, secciones, voces, eventos, clima=None):
    # Importación local: arreglo define los eventos; este módulo define las capas.
    from app.pipeline.arreglo import Evento

    colores = list(COLORES[preset])
    if clima:
        if preset == "epico" and clima.nombre in ("energico", "intenso"):
            colores[1] = Color("Timbales orquestales", 47, "timbales")
        elif preset == "balada" and clima.nombre == "luminoso":
            colores[0] = Color("Piano eléctrico suave", 4, "pulsos")
        elif preset == "electronico" and clima.nombre in ("sereno", "melancolico"):
            colores[0] = Color("Arpegio cristalino", 98, "arpegio")
    pistas, nuevos = [], []
    ocupados = {variante.melodia, variante.acompanamiento, variante.bajo}
    for indice, color in enumerate(colores):
        # Si el instrumento ya está en la base, elegir otro del mismo estilo.
        if color.programa in ocupados:
            alternativas = {
                "balada": ((49, "Cuerdas lentas"), (25, "Guitarra acústica de acero")),
                "pop": ((4, "Piano eléctrico"), (90, "Pad de sintetizador")),
                "rock_suave": ((17, "Órgano percusivo"), (30, "Guitarra con distorsión suave")),
                "lofi": ((5, "Piano eléctrico suave"), (12, "Marimba")),
                "folk": ((71, "Clarinete"), (21, "Acordeón")),
                "epico": ((61, "Sección de metales"), (48, "Sección de cuerdas")),
                "electronico": ((80, "Sintetizador de onda cuadrada"), (95, "Pad de barrido")),
            }
            color = next((replace(color, programa=p, nombre=nombre)
                          for p, nombre in alternativas[preset] if p not in ocupados), color)
        ocupados.add(color.programa)
        rol = f"color{indice + 1}"
        capa = []
        for nombre, inicio, compases, energia in secciones:
            # Segunda voz + color1 en estribillos. Dos colores en el puente.
            # Verso: solo detalles de color2 cada dos compases. Intro/outro libres.
            activa = nombre in ("A'", "A final", "B") if indice == 0 else nombre in ("A", "B")
            if not activa:
                continue
            fin = inicio + compases * 4
            for acorde in acordes:
                if not inicio <= acorde.inicio < fin:
                    continue
                if indice == 1 and nombre == "A" and int((acorde.inicio-inicio) // 4) % 2:
                    continue
                alturas = voces[acorde.inicio]
                largo = acorde.fin - acorde.inicio
                if color.patron == "sostenido":
                    posiciones = [(0, max(0.1, largo * 0.85), alturas[:2])]
                elif color.patron == "timbales":
                    posiciones = [(p, min(0.4, largo-p), [36 + acorde.fundamental])
                                  for p in (0, 2) if p < largo]
                else:
                    paso = 0.5 if color.patron == "arpegio" else 2
                    posiciones = []
                    p = 0.5 if color.patron == "detalle" else 0
                    while p < largo:
                        nota = alturas[len(posiciones) % len(alturas)]
                        posiciones.append((p, min(paso * 0.65, largo-p), [nota]))
                        p += paso
                for p, duracion, notas in posiciones:
                    for nota in notas:
                        capa.append(Evento(rol, nota, acorde.inicio+p, duracion, round(50 * energia)))
        if capa:
            pistas.append(PistaArreglo(nombre=color.nombre, rol=rol, programa=color.programa))
            nuevos.extend(capa)

    return eventos + nuevos, pistas
