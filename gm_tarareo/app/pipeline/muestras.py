"""Muestra del mismo arreglo completo: empieza en A, sin gastar CPU en toda la canción."""

from dataclasses import replace

from app.pipeline.arreglo import ResultadoArreglo


def recortar_muestra(resultado: ResultadoArreglo, segundos: float) -> ResultadoArreglo:
    pulso = 60 / resultado.arreglo.bpm
    # Comparar el gancho con el arreglo lleno; si no se pudo incluir un
    # estribillo por duración, usar el verso original.
    seccion = next((s for s in resultado.arreglo.estructura if s.funcion == "estribillo"),
                   next(s for s in resultado.arreglo.estructura if s.nombre == "A"))
    inicio = seccion.compasInicio * 4
    largo = segundos / pulso
    eventos = []
    for e in resultado.eventos:
        desde, hasta = max(inicio, e.inicio), min(inicio + largo, e.inicio + e.duracion)
        if hasta <= desde:
            continue
        # Curvas relativas: recortarlas al segmento real para no estirar un bend.
        curva = []
        for posicion, desviacion in e.expresion:
            t = e.inicio + posicion * e.duracion
            if desde <= t < hasta:
                curva.append(((t - desde) / (hasta - desde), desviacion))
        if e.expresion:
            curva = [(0.0, 0.0)] + [(p, v) for p, v in curva if 0 < p < 1] + [(1.0, 0.0)]
        eventos.append(replace(e, inicio=desde - inicio, duracion=hasta - desde, expresion=tuple(curva)))
    return ResultadoArreglo(
        resultado.arreglo.model_copy(update={"duracionSegundos": segundos}), eventos,
    )
