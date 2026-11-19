"""Casos nuevos: registros, afinaciones y ritmos ajenos al lote inicial."""

from itertools import pairwise

import numpy as np
import pytest
import soundfile as sf

from app.modelos import NotaMusical
from app.pipeline.analisis import regularizar, regularizar_fiel
from app.pipeline.expresion import conservar_expresion
from app.pipeline.interpretacion import verificar_alturas
from app.pipeline.limpieza import limpiar_notas
from app.pipeline.melodia import NotaCruda, extraer_melodia


def _audio(tmp_path, alturas, cents=0, semilla=7):
    sr = 22050
    rng = np.random.default_rng(semilla)
    tramos, notas = [], []
    for i, nota in enumerate(alturas):
        t = np.arange(int(.45*sr)) / sr
        fase = 2*np.pi*440*2**((nota-69+cents/100)/12)*t
        envolvente = np.minimum(1, t/.02) * np.minimum(1, (.45-t)/.025)
        # Fundamental, armónicos y ruido, sin depender del timbre del fixture.
        onda = (.3*np.sin(fase) + .12*np.sin(2*fase) + .05*np.sin(3*fase))*envolvente
        tramos.append(onda + rng.normal(0, .0005, len(t)))
        notas.append(NotaCruda(nota, i*.45, (i+1)*.45, .7))
    ruta = tmp_path / "idea.wav"
    sf.write(ruta, np.concatenate(tramos), sr)
    return ruta, notas


@pytest.mark.parametrize("registro", [36, 48, 60, 72, 84])
@pytest.mark.parametrize("cents", [-38, 0, 38])
def test_ideas_nuevas_en_distintos_registros_y_afinaciones(tmp_path, registro, cents):
    alturas = [registro+p for p in (0, 1, 4, 6, 7, 11, 14, 0)]  # incluye cromatismos
    ruta, notas = _audio(tmp_path, alturas, cents)
    resultado, confirmadas, informe = verificar_alturas(ruta, notas)
    assert [n.nota for n in resultado] == alturas  # no fuerza una escala conocida
    assert len(confirmadas) >= 6
    assert informe.afinacionReferenciaCents == pytest.approx(cents, abs=6)


def test_corrige_un_semitono_si_el_audio_lo_confirma(tmp_path):
    alturas = [60, 62, 63, 67, 69, 66, 64, 60]
    ruta, notas = _audio(tmp_path, alturas, cents=30)
    notas[3] = NotaCruda(68, notas[3].inicio, notas[3].fin, .65)
    resultado, _, informe = verificar_alturas(ruta, notas)
    assert [n.nota for n in resultado] == alturas
    assert any(a.original == 68 and a.corregida == 67 for a in informe.ajustes)


def test_conserva_salto_amplio_y_nota_tenue_si_la_senal_los_respalda(tmp_path, config):
    alturas = [60, 62, 60, 63, 60, 61, 79, 60]
    ruta, notas = _audio(tmp_path, alturas)
    notas[6] = NotaCruda(79, notas[6].inicio, notas[6].fin, .3)
    verificadas, confirmadas, _ = verificar_alturas(ruta, notas)
    limpias, _ = limpiar_notas(verificadas, config, confirmadas)
    assert [n.nota for n in limpias] == alturas
    sin_audio, _ = limpiar_notas(notas, config)
    assert 79 not in [n.nota for n in sin_audio]


def test_el_ruido_no_respalda_notas_arbitrarias(tmp_path):
    ruta = tmp_path / "ruido.wav"
    sf.write(ruta, np.random.default_rng(81).normal(0, .2, 22050*3), 22050)
    notas = [NotaCruda(60+i, i*.4, (i+1)*.4, .5) for i in range(6)]
    resultado, confirmadas, informe = verificar_alturas(ruta, notas)
    assert resultado == notas and not confirmadas and not informe.ajustes


def test_una_segunda_opinion_no_introduce_saltos_de_octava(tmp_path):
    from dataclasses import replace

    ruta, notas = _audio(tmp_path, [60, 62, 64, 65, 67, 64, 62, 60])
    erroneas = [replace(n, nota=n.nota+12) for n in notas]
    resultado, _, informe = verificar_alturas(ruta, notas + erroneas)
    assert all(abs(a.nota-b.nota) <= 1 for a, b in zip(resultado, notas + erroneas, strict=True))
    assert not informe.ajustes


def test_periodicidad_sin_energia_fundamental_no_confirma_subarmonicos(tmp_path, monkeypatch):
    import librosa

    from app.pipeline.interpretacion import medir_alturas

    ruta, _ = _audio(tmp_path, [60, 62, 64, 65, 67, 64, 62, 60])
    original = librosa.yin
    monkeypatch.setattr(librosa, "yin", lambda *a, **k: original(*a, **k) / 2)
    _, _, validas, _ = medir_alturas(ruta)
    assert float(np.mean(validas)) < .05


def test_baja_confianza_del_modelo_no_rechaza_una_melodia_corroborada(tmp_path, config, monkeypatch):
    from dataclasses import replace

    ruta, notas = _audio(tmp_path, [55, 57, 59, 60, 62, 59, 57, 55])
    notas = [replace(n, amplitud=.3) for n in notas]
    monkeypatch.setattr("app.pipeline.melodia.extraer_notas_crudas", lambda _: notas)
    resultado, confianza = extraer_melodia(ruta, config)
    assert resultado == notas and confianza < config.melodia_confianza_minima


def _notas(iois, duracion=.15):
    inicios = np.r_[0, np.cumsum(iois)]
    return [NotaMusical(nota=60+i%7, inicio=t, duracion=duracion, velocidad=90) for i, t in enumerate(inicios)]


def test_el_ritmo_no_acumula_desplazamiento_entre_notas():
    notas = _notas([.28]*30)
    antes, despues = regularizar(notas, 120), regularizar_fiel(notas, 120)
    esperado = (notas[-1].inicio-notas[0].inicio)*2
    assert abs(despues[-1].inicioPulsos-esperado) <= .101
    assert abs(antes[-1].inicioPulsos-esperado) > 1
    assert all(a.inicioPulsos+a.duracionPulsos <= b.inicioPulsos+1e-5 for a, b in pairwise(despues))


def test_tresillos_y_notas_largas_no_se_convierten_en_pausas():
    notas = _notas([1/6]*12)
    resultado = regularizar_fiel(notas, 120)
    assert [n.inicioPulsos for n in resultado] == pytest.approx([i/3 for i in range(13)], abs=1e-5)
    sostenida = _notas([.5, .5, 4, .5])
    sostenida[2].duracion = 3.9
    r = regularizar_fiel(sostenida, 120)
    assert r[3].inicioPulsos == 10 and r[2].duracionPulsos == pytest.approx(7.8, abs=.101)
    sostenida[2].duracion = .3
    respiracion = regularizar_fiel(sostenida, 120)
    assert respiracion[3].inicioPulsos < r[3].inicioPulsos


def test_expresion_moderada_reduce_la_desafinacion_sin_borrar_el_gesto():
    limpia = NotaMusical(nota=60, inicio=0, duracion=1, velocidad=80)
    cruda = NotaCruda(60, 0, 1, .8, tuple(.3*np.sin(np.arange(60)*.4)))
    conservar_expresion([limpia], [cruda], intensidad=.4)
    assert 0 < max(abs(p.semitonos) for p in limpia.expresion) <= .14
