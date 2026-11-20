"""Pruebas (sin GPU ni modelos) de las correcciones de la etapa 1 de MusicAI.

Ejecutar desde gm_backend/ml/translation_worker con un Python que tenga numpy, scipy, soundfile,
pydantic-settings y httpx, y FFmpeg en el PATH:

    python -m pytest -q tests
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.config import Config  # noqa: E402
from app.pipeline import igualar, mix, synthesize, transcribe  # noqa: E402

SR = 44100


def _cargar_seedvc():
    spec = importlib.util.spec_from_file_location("seedvc_cantar", RAIZ / "scripts" / "externos" / "seedvc_cantar.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ---------- 1. Whisper: alucinaciones y tramos sin letra ----------

@pytest.mark.parametrize("texto,esperado", [
    ("We'll be right back.", True), ("Thank you.", True), ("🎵", True), (" Gracias ", True),
    ("I'm levitating", False), ("Thank you for loving me", False),
])
def test_es_alucinacion(texto, esperado):
    assert transcribe.es_alucinacion(texto) is esperado


def _palabras(inicio, fin, n, segmento=0, texto="la"):
    paso = (fin - inicio) / n
    return [{"inicio": inicio + k * paso, "fin": inicio + (k + 1) * paso - 0.02, "texto": f" {texto}",
             "segmento": segmento} for k in range(n)]


def test_tramo_con_voz_sin_letra_absorbe_la_alucinacion_del_medio():
    voz = np.ones(int(40 / 0.02), dtype=bool)  # voz sonando los 40 s
    palabras = _palabras(0, 10, 20) + _palabras(20.0, 20.6, 4, 1) + _palabras(30, 40, 20, 2)
    assert transcribe.tramos_sin_letra(palabras, voz, 40.0) == [(9.98, 30.0)]


def test_tramo_sin_voz_no_se_reintenta():
    voz = np.zeros(int(40 / 0.02), dtype=bool)
    voz[: int(10 / 0.02)] = voz[int(30 / 0.02):] = True  # el hueco 10-30 s es instrumental
    palabras = _palabras(0, 10, 20) + _palabras(30, 40, 20, 1)
    assert transcribe.tramos_sin_letra(palabras, voz, 40.0) == []


def test_muchas_palabras_en_medio_no_unen_los_huecos():
    voz = np.ones(int(40 / 0.02), dtype=bool)
    palabras = _palabras(0, 10, 20) + _palabras(16, 22, 12, 1) + _palabras(30, 40, 20, 2)
    assert transcribe.tramos_sin_letra(palabras, voz, 40.0) == [(9.98, 16.0), (21.98, 30.0)]


class _WhisperFalso:
    """Devuelve, para cualquier trozo, un segmento con `n` palabras repartidas en el trozo."""

    def __init__(self, n):
        self.n = n

    def transcribe(self, audio, language=None, **_):
        dur = len(audio) / 16000
        palabras = [SimpleNamespace(start=k * dur / self.n, end=(k + 0.8) * dur / self.n, word=f" w{k}")
                    for k in range(self.n)]
        return [SimpleNamespace(text="letra", words=palabras)], SimpleNamespace(language=language)


def _audio_voz(segundos):
    t = np.arange(int(segundos * 16000)) / 16000
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_recuperar_tramos_sustituye_la_alucinacion_por_la_letra():
    audio = _audio_voz(40)
    palabras = _palabras(0, 10, 20) + _palabras(20.0, 20.6, 4, 1, "back") + _palabras(30, 40, 20, 2)
    nuevas, informe = transcribe.recuperar_tramos(_WhisperFalso(60), audio, 16000, palabras, "en", {})
    assert informe[0]["aceptado"] and informe[0]["palabras_antes"] == 4
    assert not any(p["texto"] == " back" for p in nuevas)
    dentro = [p for p in nuevas if 10 < p["inicio"] < 30]
    assert len(dentro) >= 40
    assert all(a["inicio"] <= b["inicio"] for a, b in zip(nuevas, nuevas[1:]))


def test_recuperar_tramos_descarta_pocas_palabras_sobre_mucha_voz():
    audio = _audio_voz(40)
    palabras = _palabras(0, 10, 20) + _palabras(30, 40, 20, 1)
    nuevas, informe = transcribe.recuperar_tramos(_WhisperFalso(2), audio, 16000, palabras, "en", {})
    assert not informe[0]["aceptado"]
    assert nuevas == palabras


# ---------- 2. Versos que no caben ----------

def _verso(texto, sr=24000, palabra_s=0.25, pausa_s=0.08):
    """Audio falso de un verso: una ráfaga de ruido por palabra, separadas por silencios."""
    azar = np.random.default_rng(len(texto))
    trozos = []
    for _ in texto.split():
        trozos += [0.5 * azar.standard_normal(int(palabra_s * sr)), np.zeros(int(pausa_s * sr))]
    return np.concatenate(trozos[:-1]).astype(np.float32)


def test_punto_de_corte_cae_en_una_pausa_entre_palabras():
    audio = _verso("uno dos tres cuatro cinco seis", sr=SR)
    maximo = int(1.5 * SR)  # a mitad de la quinta palabra
    corte = synthesize.punto_de_corte(audio, maximo)
    assert corte is not None and corte <= maximo
    assert np.abs(audio[corte - int(0.005 * SR): corte]).max() < 1e-6  # justo antes: silencio


def test_punto_de_corte_sin_pausas_devuelve_none():
    audio = 0.5 * np.random.default_rng(0).standard_normal(3 * SR).astype(np.float32)
    assert synthesize.punto_de_corte(audio, 2 * SR) is None


def test_espacio_disponible_usa_el_silencio_hasta_el_verso_siguiente():
    frases = [{"inicio": 0.0, "fin": 1.0}, {"inicio": 2.0, "fin": 3.0}]
    assert synthesize.espacio_disponible(frases, 0, 10.0) == pytest.approx(1.95)
    assert synthesize.espacio_disponible(frases, 1, 3.5) == pytest.approx(1.45)


class _SintetizadorFalso(synthesize.Sintetizador):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.llamadas = []

    def generar_frases(self, frases, referencia, idioma):
        self.llamadas.append([f["texto"] for f in frases])
        return [(_verso(f["texto"]), 24000) for f in frases]


def _preparar(tmp_path, texto_largo):
    voz = tmp_path / "voz.wav"
    sf.write(str(voz), 0.2 * np.ones(int(8 * SR), dtype=np.float32), SR)
    letra = {"idioma_origen": "en", "idioma_destino": "es", "resumen": "",
             "frases": [{"inicio": 0.5, "fin": 2.0, "original": "one two three", "texto": "uno dos tres"},
                        {"inicio": 2.6, "fin": 4.0, "original": "four five six", "texto": texto_largo},
                        {"inicio": 4.4, "fin": 6.0, "original": "seven", "texto": "siete ocho"}]}
    ruta = tmp_path / "letra.json"
    ruta.write_text(json.dumps(letra, ensure_ascii=False), encoding="utf-8")
    return ruta, voz


def test_verso_largo_se_acorta_con_el_llm_y_no_se_recorta(tmp_path):
    largo = "cuatro cinco seis siete ocho nueve diez once doce"  # 9 palabras ≈ 3 s en un hueco de 1.75 s
    ruta, voz = _preparar(tmp_path, largo)
    pedidos_vistos = []

    def acortar(letra, pedidos):
        pedidos_vistos.extend(pedidos)
        return {p["i"]: "cuatro cinco seis" for p in pedidos}

    s = _SintetizadorFalso(Config(tempo_max=1.4, igualar_voz=False))
    s.sintetizar(ruta, voz, tmp_path / "salida.wav", acortar=acortar)
    assert [p["i"] for p in pedidos_vistos] == [1]
    assert s.llamadas[-1] == ["cuatro cinco seis"]  # solo se vuelve a sintetizar el verso largo
    assert json.loads(ruta.read_text(encoding="utf-8"))["frases"][1]["texto"] == "cuatro cinco seis"
    informe = json.loads((tmp_path / "frases" / "informe_versos.json").read_text(encoding="utf-8"))
    assert all(d["accion"] == "cabe" for d in informe)


def test_sin_llm_se_rescata_o_se_corta_en_una_pausa(tmp_path):
    largo = "cuatro cinco seis siete ocho nueve diez once doce"
    ruta, voz = _preparar(tmp_path, largo)
    s = _SintetizadorFalso(Config(tempo_max=1.4, igualar_voz=False))
    s.sintetizar(ruta, voz, tmp_path / "salida.wav", acortar=lambda letra, pedidos: {})
    informe = json.loads((tmp_path / "frases" / "informe_versos.json").read_text(encoding="utf-8"))
    verso = informe[1]
    assert verso["accion"] in {"tempo_rescate", "adelantado", "cortada_en_pausa"}
    assert verso["accion"] != "cortada_a_mitad"
    assert json.loads(ruta.read_text(encoding="utf-8"))["frases"][1]["texto"] == largo  # sin cambios


def test_acortar_frases_usa_el_llm_y_descarta_lo_que_no_acorta(monkeypatch):
    from app.pipeline import translate

    class Falso:
        def traducir_lote(self, lineas, origen, destino, contexto="", resumen=""):
            assert all("aviso" in l and "at most" in l["aviso"] for l in lineas)
            return {1: "corta ya", 2: "esta respuesta es todavía más larga que la original de antes"}

        def liberar(self):
            pass

    monkeypatch.setattr(translate, "crear_traductor", lambda cfg: Falso())
    letra = {"idioma_origen": "en", "idioma_destino": "es", "resumen": "r", "frases": []}
    pedidos = [{"i": 7, "texto": "una frase bastante larga de verdad", "original": "a", "silabas": 4, "segundos": 1},
               {"i": 9, "texto": "otra frase larga", "original": "b", "silabas": 3, "segundos": 1}]
    assert translate.acortar_frases(letra, pedidos, Config()) == {7: "corta ya"}


def test_acortar_frases_no_espera_mas_del_limite(monkeypatch):
    import time

    from app.pipeline import translate

    class Lento:
        def traducir_lote(self, *a, **k):
            time.sleep(2)
            return {1: "x"}

        def liberar(self):
            pass

    monkeypatch.setattr(translate, "crear_traductor", lambda cfg: Lento())
    letra = {"idioma_origen": "en", "idioma_destino": "es", "frases": []}
    inicio = time.perf_counter()
    assert translate.acortar_frases(letra, [{"i": 0, "texto": "a b c d", "original": "", "silabas": 2,
                                             "segundos": 1}], Config(), timeout_s=0.3) == {}
    assert time.perf_counter() - inicio < 1.5


# ---------- 4. Volumen ----------

def test_nivel_por_frase_iguala_los_saltos_de_volumen():
    t = np.arange(int(6 * SR)) / SR
    tono = np.sin(2 * np.pi * 300 * t)
    frases = [{"inicio": 0.0, "fin": 2.0}, {"inicio": 2.0, "fin": 4.0}, {"inicio": 4.0, "fin": 6.0}]
    original = 0.3 * tono                                   # la original: los tres versos al mismo volumen
    nueva = tono * np.repeat([0.3, 0.075, 0.3], 2 * SR)     # la nueva: el verso del medio 12 dB más bajo
    ganancia, correcciones = igualar.curva_nivel_por_frase(nueva, original, SR, frases, max_db=6.0)
    assert correcciones[1] == pytest.approx(6.0, abs=0.1)  # sube lo que permite el tope
    resultado = nueva * ganancia
    assert np.abs(np.diff(ganancia)).max() < 0.01  # sin saltos bruscos: rampa
    medio = np.sqrt(np.mean(resultado[int(2.5 * SR): int(3.5 * SR)] ** 2))
    assert 20 * np.log10(0.3 / np.sqrt(2) / medio) == pytest.approx(6.0, abs=0.5)


def _lufs(ruta: Path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return float(r.stderr.rsplit("I:", 1)[1].split("LUFS")[0])


def test_mezcla_en_dos_pasadas_llega_al_objetivo(tmp_path):
    t = np.arange(int(20 * SR)) / SR
    voz = (np.sin(2 * np.pi * 440 * t) * np.where(t < 10, 0.05, 0.4)).astype(np.float32)  # verso suave y fuerte
    inst = (0.1 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    sf.write(str(tmp_path / "voz.wav"), voz, SR)
    sf.write(str(tmp_path / "inst.wav"), np.stack([inst, inst], axis=1), SR)
    cfg = Config(lufs_objetivo=-14.0)
    assert mix.medir_loudnorm(tmp_path / "voz.wav", tmp_path / "inst.wav", cfg) is not None
    salida = mix.mezclar(tmp_path / "voz.wav", tmp_path / "inst.wav", tmp_path / "mezcla.wav", cfg)
    assert _lufs(salida) == pytest.approx(-14.0, abs=1.0)
    # lineal: la diferencia de volumen entre el verso suave y el fuerte se conserva (en modo dinámico se aplana)
    mezcla, _ = sf.read(str(salida))
    suave = np.sqrt(np.mean(mezcla[int(2 * SR): int(8 * SR)] ** 2))
    fuerte = np.sqrt(np.mean(mezcla[int(12 * SR): int(18 * SR)] ** 2))
    assert 20 * np.log10(fuerte / suave) > 8.0


# ---------- 4. Uniones de Seed-VC ----------

def test_elegir_corte_termina_el_trozo_en_el_silencio():
    seedvc = _cargar_seedvc()
    energia = np.zeros(3000)
    energia[:] = -2.0
    energia[700:730] = -11.0  # silencio entre el 70 % y el 73 % de la ventana
    largo = seedvc.elegir_corte(energia, hechos=0, ventana=1000, solape=16)
    assert 715 <= largo <= 731  # el fundido de 16 cuadros queda dentro del silencio
    assert seedvc.elegir_corte(energia, hechos=2500, ventana=1000, solape=16) == 500  # último trozo


# ---------- 1b. Partes cantadas que la letra publicada no trae (rap de «Levitating» en LRCLIB) ----------

def _oidas(texto, desde, paso=0.4, segmento=0):
    return [{"inicio": desde + k * paso, "fin": desde + k * paso + paso * 0.9, "texto": " " + w, "segmento": segmento}
            for k, w in enumerate(texto.split())]


def test_alinear_letra_conserva_lo_cantado_que_no_esta_en_la_letra():
    from app.pipeline.letra import alinear_letra

    letra = "I got you moonlight you are my starlight\nthe milky way we are renegading\nyeah yeah yeah yeah"
    oido = (_oidas("I got you moonlight you are my starlight", 0.0, segmento=0)
            + _oidas("the milky way we are renegading", 4.0, segmento=1)
            + _oidas("one of the greatest aint no debating on it still levitated heavily medicated "
                        "shaded ironic gave them love and they end up hating", 7.0, segmento=2)
            + _oidas("yeah yeah yeah yeah", 20.0, segmento=3))
    versos = alinear_letra(oido, letra)
    textos = ["".join(p["texto"] for p in v).strip() for v in versos]
    assert any("debating" in t for t in textos)                            # el rap se conserva
    renegading = next(v for v, t in zip(versos, textos) if t.endswith("renegading"))
    assert renegading[-1]["fin"] - renegading[0]["inicio"] < 3.0          # el verso de la letra no se estira sobre el rap
    assert [v[0]["inicio"] for v in versos] == sorted(v[0]["inicio"] for v in versos)


def test_alinear_letra_sin_partes_extra_no_cambia():
    from app.pipeline.letra import alinear_letra

    letra = "I got you moonlight you are my starlight\nthe milky way we are renegading"
    oido = _oidas("I got you moonlight you are my starlight", 0.0) + _oidas("the milky way we are renegading", 4.0, segmento=1)
    assert len(alinear_letra(oido, letra)) == 2


def test_alinear_letra_no_estira_el_ultimo_verso_sobre_el_final():
    """5d0c3f64: el último verso de la letra se repartió sobre 31 s (palabras sueltas oídas en el cierre)."""
    from app.pipeline.letra import alinear_letra

    letra = "I got you moonlight you are my starlight\ncome on dance with me tonight baby"
    oido = (_oidas("I got you moonlight you are my starlight", 0.0)
            + _oidas("come on", 4.0, segmento=1) + _oidas("yeah", 15.0, segmento=2) + _oidas("whoa", 30.0, segmento=3)
            + _oidas("ooh", 34.0, segmento=4))
    versos = alinear_letra(oido, letra)
    assert max(v[-1]["fin"] - v[0]["inicio"] for v in versos) < 12.0


# ---------- 5. Validación final: secciones desaparecidas ----------

def test_validar_detecta_seccion_sin_voz_y_caida_de_volumen():
    from app.pipeline import validar

    sr = 16000
    t = np.arange(40 * sr) / sr
    voz_o = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    voz_n = voz_o.copy()
    voz_n[int(10 * sr): int(20 * sr)] = 0  # la voz traducida desaparece 10 s
    inst = (0.1 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    perdidas = validar.secciones_sin_voz(voz_o, voz_n, sr)
    assert len(perdidas) == 1 and 9.5 <= perdidas[0]["desde"] <= 10.6 and 19.4 <= perdidas[0]["hasta"] <= 20.5
    original = voz_o + inst
    mezcla = 0.5 * (voz_n + inst * 0.05)  # otro volumen general + sin instrumental ni voz en el tramo
    mezcla[: int(10 * sr)] = 0.5 * original[: int(10 * sr)]
    mezcla[int(20 * sr):] = 0.5 * original[int(20 * sr):]
    caidas = validar.caidas_de_volumen(original, mezcla, sr)
    assert len(caidas) == 1 and caidas[0]["caida_db"] >= 12
    assert validar.secciones_sin_voz(voz_o, voz_o, sr) == []
    assert validar.caidas_de_volumen(original, 0.5 * original, sr) == []
    assert validar.versos_largos([{"inicio": 28.4, "fin": 96.1, "texto": "la Vía Láctea"}])[0]["segundos"] == 67.7


def test_rellenar_sin_letra_usa_la_voz_original_solo_fuera_de_los_versos(tmp_path):
    from app.pipeline import validar

    sr = 16000
    t = np.arange(20 * sr) / sr
    orig = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)   # la cantante canta los 20 s
    nueva = np.zeros_like(orig)
    nueva[: int(10 * sr)] = 0.2 * np.sin(2 * np.pi * 330 * t[: int(10 * sr)])  # verso traducido 0-10 s
    sf.write(str(tmp_path / "o.wav"), orig, sr)
    sf.write(str(tmp_path / "n.wav"), nueva, sr)
    frases = [{"inicio": 0.0, "fin": 10.0, "texto": "verso"}]
    ruta, tramos = validar.rellenar_sin_letra(tmp_path / "n.wav", tmp_path / "o.wav", frases, tmp_path / "s.wav")
    assert len(tramos) == 1 and 10.2 <= tramos[0]["desde"] <= 10.5
    x, _ = sf.read(str(ruta))
    assert np.allclose(x[int(2 * sr): int(8 * sr)], nueva[int(2 * sr): int(8 * sr)], atol=1e-3)  # el verso no se toca
    assert np.sqrt(np.mean(x[int(12 * sr): int(18 * sr)] ** 2)) > 0.15                       # el hueco ya no está mudo
