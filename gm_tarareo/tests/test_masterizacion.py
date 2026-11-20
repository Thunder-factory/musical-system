"""Comprueba el efecto sobre audio real de los filtros, sin modelos de IA."""

import subprocess

import numpy as np
import pytest

from app.pipeline.masterizacion import filtros_masterizacion

SR = 44100


def _procesar(audio, activada=True):
    """Ejecuta la misma cadena de ffmpeg del render, sin normalizar ni comprimir a MP3."""
    resultado = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "f64le", "-ar", str(SR), "-ac", "2", "-i", "pipe:0",
         "-af", ",".join(filtros_masterizacion(activada)) or "anull", "-f", "f64le", "pipe:1"],
        input=np.asarray(audio, dtype="<f8").tobytes(), capture_output=True, check=True,
    )
    return np.frombuffer(resultado.stdout, dtype="<f8").reshape(-1, 2)


def _rms(audio):
    return float(np.sqrt(np.mean(np.square(audio))))


def test_limpia_subgraves_sin_quitar_la_melodia():
    t = np.arange(3 * SR) / SR
    mono = 0.008 * (np.sin(2 * np.pi * 20 * t) + np.sin(2 * np.pi * 1000 * t))
    entrada = np.column_stack([mono, mono])
    salida = _procesar(entrada)

    def amplitud(audio, frecuencia):
        # Descartar el arranque del filtro y medir la energía de cada tono.
        ventana = audio[SR:, 0]
        fase = 2 * np.pi * frecuencia * t[SR:]
        return 2 * np.hypot(np.mean(ventana * np.sin(fase)), np.mean(ventana * np.cos(fase)))

    assert amplitud(salida, 20) / amplitud(entrada, 20) < 0.45
    assert amplitud(salida, 1000) / amplitud(entrada, 1000) == pytest.approx(1, abs=0.15)
    assert salida.shape == entrada.shape


def test_comprime_suave_sin_mover_el_panorama():
    t = np.arange(6 * SR) / SR
    tono = np.sin(2 * np.pi * 1000 * t)
    tono *= np.where(t < 3, 0.01, 0.10)
    entrada = np.column_stack([tono, tono * 0.4])  # instrumento a la izquierda
    salida = _procesar(entrada)

    contraste_entrada = 20 * np.log10(_rms(entrada[4 * SR:5 * SR]) / _rms(entrada[SR:2 * SR]))
    contraste_salida = 20 * np.log10(_rms(salida[4 * SR:5 * SR]) / _rms(salida[SR:2 * SR]))
    reduccion = contraste_entrada - contraste_salida
    assert 0.5 < reduccion < 4  # suaviza el cambio fuerte; no aplasta la expresión
    assert np.allclose(salida[:, 1], salida[:, 0] * 0.4, atol=1e-9)
    assert np.isfinite(salida).all()


def test_se_puede_desactivar_y_el_silencio_sigue_siendo_silencio():
    rng = np.random.default_rng(42)
    entrada = rng.normal(0, 0.005, (SR, 2))
    assert np.array_equal(_procesar(entrada, activada=False), entrada)
    assert np.count_nonzero(_procesar(np.zeros((SR, 2)))) == 0
