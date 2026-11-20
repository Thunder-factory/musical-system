"""Operaciones sobre la letra (puras, sin modelos): alinear una letra dada con lo que oyó Whisper,
separar interjecciones y unir versos demasiado cortos."""
import logging
import re
from difflib import SequenceMatcher

from app.errores import EntradaInvalida

log = logging.getLogger("worker.letra")

_FICHA = re.compile(r"[぀-ヿ㐀-鿿가-힯]|[^\s぀-ヿ㐀-鿿가-힯]+")
_ETIQUETA = re.compile(r"[\[(（【].*[\])）】]")  # [Coro], (x2)...
_S_POR_PALABRA = 0.35  # duración supuesta de una palabra cuando no hay nada con qué medirla
_MAX_S_POR_PALABRA = 1.5  # MusicAI: lo más que puede durar una palabra cantada al repartir la letra


def _norm(texto: str) -> str:
    return re.sub(r"[\W_]", "", texto.lower())


def _fichas_de_whisper(palabras: list[dict]) -> list[dict]:
    """Palabras de Whisper troceadas igual que la letra (un carácter chino = una ficha)."""
    fichas = []
    for n, p in enumerate(palabras):
        trozos = [t for t in _FICHA.findall(p["texto"]) if _norm(t)]
        paso = (p["fin"] - p["inicio"]) / max(1, len(trozos))
        for k, t in enumerate(trozos):
            fichas.append({"inicio": p["inicio"] + k * paso, "fin": p["inicio"] + (k + 1) * paso,
                           "clave": _norm(t), "palabra": n})
    return fichas


def _por_segmento(palabras: list[dict]) -> list[list[dict]]:
    """Agrupación mínima de palabras de Whisper en versos: una por segmento."""
    grupos: list[list[dict]] = []
    for p in palabras:
        if grupos and grupos[-1][-1].get("segmento") == p.get("segmento"):
            grupos[-1].append(p)
        else:
            grupos.append([p])
    return grupos


def _repartir(n: int, desde: float, hasta: float) -> list[tuple[float, float]]:
    """n tramos iguales entre dos instantes."""
    paso = max(0.0, hasta - desde) / max(1, n)
    return [(desde + k * paso, desde + (k + 1) * paso) for k in range(n)]


def alinear_letra(palabras: list[dict], letra: str, agrupar=None, min_oidas: int = 8,
                  min_oido_s: float = 4.0, max_proporcion: float = 0.5) -> list[list[dict]]:
    """Pone tiempos a una letra escrita usando las palabras (con tiempos) que oyó Whisper.

    Cada línea de `letra` es un verso. Las palabras que coinciden toman el tiempo de Whisper; las que
    Whisper oyó mal se reparten en el tramo donde oyó otra cosa. Las líneas que quedan fuera de lo
    que suena en el video (la letra puede ser de la canción entera) se descartan.
    Devuelve los versos como listas de palabras [{inicio, fin, texto}].

    MusicAI: la letra publicada puede no traer partes que sí se cantan en el video (p. ej. el rap de
    «Levitating», que no está en la letra de LRCLIB). Antes, el verso anterior se estiraba sobre toda esa
    parte (un verso de 68 s) y se perdía lo cantado. Ahora, si entre dos anclas Whisper oyó al menos
    `min_oidas` palabras durante `min_oido_s` y la letra tiene menos de `max_proporcion` de esas palabras,
    las de la letra se colocan junto a su ancla y el resto del tramo se toma de lo que oyó Whisper
    (agrupado con `agrupar`, por defecto un verso por segmento).
    """
    agrupar = agrupar or _por_segmento
    lineas = [l.strip() for l in letra.splitlines()]
    lineas = [l for l in lineas if l and not _ETIQUETA.fullmatch(l)]
    letra_f = [(n, t) for n, l in enumerate(lineas) for t in _FICHA.findall(l)]
    oido = _fichas_de_whisper(palabras)
    a = [_norm(t) or f"\0{i}" for i, (_, t) in enumerate(letra_f)]  # la puntuación suelta nunca coincide
    b = [f["clave"] for f in oido]

    # anclas: coincidencias fiables (dos palabras seguidas, o una sola pero larga)
    anclas: list[tuple[int, int]] = []
    for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        if blk.size >= 2 or (blk.size == 1 and len(a[blk.a]) >= 5):
            anclas += [(blk.a + k, blk.b + k) for k in range(blk.size)]
    if not oido or len(anclas) < max(2, 0.2 * len(oido)):
        raise EntradaInvalida("letra_original no coincide con lo que se canta en el video")
    log.info("letra_original: %d de %d palabras oídas coinciden con la letra", len(anclas), len(oido))

    tiempos: dict[int, tuple[float, float]] = {i: (oido[j]["inicio"], oido[j]["fin"]) for i, j in anclas}
    primera, ultima = letra_f[anclas[0][0]][0], letra_f[anclas[-1][0]][0]

    def rellenar(i1: int, i2: int, j1: int, j2: int, antes: float | None, despues: float | None) -> None:
        """Fichas de la letra [i1, i2) sin ancla ↔ tramo donde Whisper oyó las fichas [j1, j2)."""
        n = i2 - i1
        if n <= 0:
            return
        if j2 > j1:
            desde, hasta = oido[j1]["inicio"], oido[j2 - 1]["fin"]
            # MusicAI: unas pocas palabras de la letra nunca se estiran sobre medio minuto de canción
            # (verso de 68 s en 5d0c3f64): se quedan junto a su ancla con una duración razonable
            maximo = n * _MAX_S_POR_PALABRA + 1.0
            if hasta - desde > maximo:
                if antes is None and despues is not None:
                    hasta = despues
                    desde = hasta - maximo
                else:
                    desde = antes if antes is not None else desde
                    hasta = desde + maximo
        elif antes is not None and despues is not None:
            # Whisper no oyó nada aquí: no estirar las palabras sobre todo el hueco, centrarlas
            sobra = max(0.0, (despues - antes) - 2 * _S_POR_PALABRA * n)
            desde, hasta = antes + sobra / 2, despues - sobra / 2
        elif despues is not None:
            desde, hasta = max(0.0, despues - _S_POR_PALABRA * n), despues
        else:
            desde, hasta = antes, antes + _S_POR_PALABRA * n
        for k, t in enumerate(_repartir(n, desde, hasta)):
            tiempos[i1 + k] = t

    # antes de la primera ancla (solo lo que pertenece a su misma línea) y después de la última
    i0, j0 = anclas[0]
    ini = next(i for i, (n, _) in enumerate(letra_f) if n == primera)
    rellenar(ini, i0, max(0, j0 - (i0 - ini)), j0, None, oido[j0]["inicio"])
    sin_letra: list[tuple[int, int]] = []  # fichas oídas [j1, j2) que la letra no trae
    for (ia, ja), (ib, jb) in zip(anclas, anclas[1:]):
        n_letra, n_oido = ib - ia - 1, jb - ja - 1
        if (n_oido >= min_oidas and oido[jb - 1]["fin"] - oido[ja + 1]["inicio"] >= min_oido_s
                and n_letra < max_proporcion * n_oido):
            # las fichas de la letra van pegadas a su ancla: las de la línea de `ia` justo después de ella,
            # el resto justo antes de `ib`; lo que queda en medio es una parte que la letra no tiene
            tras = sum(1 for i in range(ia + 1, ib) if letra_f[i][0] == letra_f[ia][0])
            antes_b = n_letra - tras
            rellenar(ia + 1, ia + 1 + tras, ja + 1, ja + 1 + tras, oido[ja]["fin"], None)
            rellenar(ia + 1 + tras, ib, jb - antes_b, jb, None, oido[jb]["inicio"])
            sin_letra.append((ja + 1 + tras, jb - antes_b))
            continue
        rellenar(ia + 1, ib, ja + 1, jb, oido[ja]["fin"], oido[jb]["inicio"])
    i9, j9 = anclas[-1]
    fin = max(i for i, (n, _) in enumerate(letra_f) if n == ultima) + 1
    rellenar(i9 + 1, fin, j9 + 1, min(len(oido), j9 + 1 + (fin - i9 - 1)), oido[j9]["fin"], None)

    versos: list[list[dict]] = [[] for _ in lineas]
    for i, (n, t) in enumerate(letra_f):
        if i in tiempos:
            pegado = bool(_FICHA.fullmatch(t)) and len(t) == 1 and not t.isascii() and t.isalpha() and \
                bool(re.match(r"[぀-ヿ㐀-鿿]", t))
            versos[n].append({"inicio": tiempos[i][0], "fin": tiempos[i][1],
                              "texto": t if pegado else " " + t})
    versos = [v for v in versos[primera: ultima + 1] if v]
    for j1, j2 in sin_letra:
        if j2 <= j1:
            continue
        p1, p2 = oido[j1]["palabra"], oido[j2 - 1]["palabra"]
        extra = agrupar([dict(p) for p in palabras[p1: p2 + 1]])
        log.info("letra_original: %.1f-%.1fs se canta pero no está en la letra (%d palabras): se usa lo que "
                 "oyó Whisper", palabras[p1]["inicio"], palabras[p2]["fin"], p2 - p1 + 1)
        versos += [[{"inicio": p["inicio"], "fin": p["fin"], "texto": p["texto"]} for p in g] for g in extra if g]
    return sorted(versos, key=lambda v: v[0]["inicio"])


FUENTES_LETRA = ("usuario", "lrclib", "whisper")


def letra_publica(datos: dict, fuente_letra: str, titulo: str | None = None,
                  artista: str | None = None) -> dict:
    """letra.json que se entrega: añade de dónde salió la letra y, si vino de LRCLIB, quita el texto
    original de cada frase (esa letra no es nuestra: se usa para traducir, no se redistribuye)."""
    publica = {**datos, "fuente_letra": fuente_letra,
               **({"titulo": titulo} if titulo else {}), **({"artista": artista} if artista else {})}
    if fuente_letra == "lrclib":
        publica["frases"] = [{k: v for k, v in f.items() if k != "original"} for f in datos.get("frases", [])]
    return publica


def unir_frases_cortas(frases: list[dict], min_s: float = 1.0, hueco_max_s: float = 1.0,
                       max_s: float = 9.0) -> list[dict]:
    """Une cada verso de menos de `min_s` con su vecino más cercano en el tiempo.

    Un trozo tan corto casi nunca es una frase: es una palabra que quedó separada de la suya.
    No se une si el vecino está a más de `hueco_max_s` ni si es una interjección (`conservar`).
    """
    frases = [dict(f) for f in frases]
    if min_s <= 0:
        return frases
    i = 0
    while i < len(frases):
        f = frases[i]
        if f.get("conservar") or f["fin"] - f["inicio"] >= min_s:
            i += 1
            continue
        opciones = []
        if i > 0 and not frases[i - 1].get("conservar"):
            hueco = f["inicio"] - frases[i - 1]["fin"]
            if hueco <= hueco_max_s and f["fin"] - frases[i - 1]["inicio"] <= max_s:
                opciones.append((hueco, 0, i - 1))
        if i + 1 < len(frases) and not frases[i + 1].get("conservar"):
            hueco = frases[i + 1]["inicio"] - f["fin"]
            if hueco <= hueco_max_s and frases[i + 1]["fin"] - f["inicio"] <= max_s:
                opciones.append((hueco, 1, i + 1))
        if not opciones:
            i += 1
            continue
        a, b = sorted((i, min(opciones)[2]))
        izq, der = frases[a]["texto"], frases[b]["texto"]
        pegar = "" if re.search(r"[぀-ヿ㐀-鿿]$", izq) else " "
        frases[a] = {"inicio": frases[a]["inicio"], "fin": frases[b]["fin"], "texto": izq + pegar + der}
        del frases[b]
        i = a  # si sigue siendo corto, se vuelve a intentar
    return frases


# ---------- Interjecciones: se conservan del audio original en vez de traducirse y sintetizarse ----------

_INTERJ = re.compile(r"(o+h+|a+h+|u+h+|e+h+|h+e+y+|e+y+|y+e+a+h*|w+h?o+a+h*|w+o+a*h+|m+h?m+|h+m+|w+o+o+|"
                     r"h+o+o+|u+o+h+|a+y+|[啊哦噢喔耶嘿呜哟])")
# sílabas de relleno que también son palabras normales ("la"): solo cuentan repetidas ("la la la")
_VOCABLES = {"la", "na", "da", "du", "doo", "sha", "ha", "ba", "pa", "ra", "ta", "啦"}


def marcar_interjecciones(textos: list[str]) -> list[bool]:
    """Por cada palabra, si es una interjección o vocalización (oh, hey, yeah, la la...)."""
    claves = [_norm(t) for t in textos]
    marcas = []
    for i, c in enumerate(claves):
        repetida = c in _VOCABLES and (c in claves[max(0, i - 1): i] or c in claves[i + 1: i + 2])
        marcas.append(bool(_INTERJ.fullmatch(c)) or repetida)
    return marcas


def separar_interjecciones(verso: list[dict], min_borde_s: float = 0.25,
                           min_medio_s: float = 0.8) -> list[tuple[list[dict], bool]]:
    """Parte un verso (lista de palabras) en tramos (palabras, conservar).

    Las interjecciones al principio o al final se separan casi siempre; las de en medio, solo si son
    largas (si no, se quedan dentro de la frase para no trocearla).
    """
    marcas = marcar_interjecciones([p["texto"] for p in verso])
    tramos: list[tuple[list[dict], bool]] = []
    for p, m in zip(verso, marcas):
        if tramos and tramos[-1][1] == m:
            tramos[-1][0].append(p)
        else:
            tramos.append(([p], m))
    if len(tramos) == 1:
        return tramos
    for k, (grupo, m) in enumerate(tramos):  # las interjecciones demasiado cortas vuelven a la frase
        borde = k in (0, len(tramos) - 1)
        if m and grupo[-1]["fin"] - grupo[0]["inicio"] < (min_borde_s if borde else min_medio_s):
            tramos[k] = (grupo, False)
    unidos: list[tuple[list[dict], bool]] = []
    for grupo, m in tramos:
        if unidos and unidos[-1][1] == m:
            unidos[-1][0].extend(grupo)
        else:
            unidos.append((list(grupo), m))
    return unidos


def escribir_interjeccion(texto: str, segundos: float) -> str:
    """Reescribe una interjección para que el TTS la diga como sonido y no como palabra:
    sin signos, en minúsculas y con la vocal alargada según lo que dura ("Oh!" → "oooh", "Hey!" → "heeey").
    """
    claves = [c for c in (_norm(t) for t in _FICHA.findall(texto)) if c]
    if not claves:
        return texto.strip()
    por_palabra = segundos / len(claves)
    letras = int(min(6, max(3, round(por_palabra / 0.2))))
    partes = []
    for c in claves:
        vocales = re.search(r"[aeiou]+", c) if c.isascii() else None
        if not vocales or por_palabra < 0.35:   # "mmm", chino, o tan breve que no hay nada que alargar
            partes.append(c)
            continue
        grupo = vocales.group()
        # "ooh" suena distinto de "oh": se conserva la diferencia con una letra más
        largo = grupo[:-1] + grupo[-1] * (letras + (1 if len(set(grupo)) == 1 and len(grupo) > 1 else 0)
                                          - len(grupo) + 1)
        partes.append(c[:vocales.start()] + largo + c[vocales.end():])
    return ", ".join(partes)
