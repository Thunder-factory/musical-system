"""Demo en vivo (app/demo.py): solo en modo desarrollo, por el mismo camino que /procesar."""

import os
import subprocess
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app, trabajos
from tests.conftest import RAIZ


@pytest.fixture
def client():
    trabajos.clear()
    with TestClient(app) as c:
        yield c


def test_la_pagina_de_la_demo_se_sirve(client):
    r = client.get("/demo")
    assert r.status_code == 200
    assert "Tarareá una idea" in r.text


def test_un_tarareo_subido_sigue_el_mismo_camino_que_procesar(client, audio_silencio):
    """El silencio falla en preprocesado: prueba que la subida crea un job real del pipeline."""
    r = client.post("/demo/tarareo", content=audio_silencio.read_bytes(), headers={"Content-Type": "audio/wav"})

    assert r.status_code == 202
    job = client.get(f"/jobs/{r.json()['jobId']}").json()
    assert job["estado"] == "FALLIDO"
    assert job["codigoError"] == "ENTRADA_INVALIDA"
    assert job["metadatos"]["motivo"] == "SIN_SENAL"


def test_sin_audio_da_422(client):
    assert client.post("/demo/tarareo", content=b"").status_code == 422


@pytest.mark.parametrize("nombre", ["config.py", "..%2F..%2Fapp%2Fconfig.py", "render.wav"])
def test_solo_se_pueden_bajar_las_salidas_conocidas(client, nombre):
    assert client.get(f"/demo/archivo/{uuid4()}/{nombre}").status_code == 404


def test_en_produccion_la_demo_no_existe():
    """Con TARAREO_MODO_DESARROLLO=false, main.py no registra ninguna ruta /demo."""
    entorno = dict(os.environ, TARAREO_MODO_DESARROLLO="false")
    salida = subprocess.run(
        [sys.executable, "-c", "from app.main import app; print(any(r.path.startswith('/demo') for r in app.routes))"],
        cwd=RAIZ, env=entorno, capture_output=True, text=True, check=True,
    )
    assert salida.stdout.strip() == "False"


@pytest.mark.slow
def test_versiones_y_eleccion_del_usuario(client, audio_real, requiere_render, config):
    """Un tarareo real da varias versiones; la elegida queda guardada con los rasgos, lista para calibrar."""
    r = client.post("/demo/tarareo", content=audio_real.read_bytes(), headers={"Content-Type": "audio/wav"})
    job_id = r.json()["jobId"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["estado"] == "COMPLETADO"
    versiones = job["metadatos"]["versiones"]
    assert len(versiones) >= 2 and versiones[0]["numero"] == 1
    assert all(v["tipo"] == "muestra" for v in versiones)
    assert client.get(f"/demo/archivo/{job_id}/muestra-2.mp3").status_code == 200
    assert client.get(f"/demo/archivo/{job_id}/cancion-2.mp3").status_code == 404
    assert client.get(f"/demo/archivo/{job_id}/partitura.musicxml").status_code == 200

    respuesta = client.post(f"/demo/eleccion/{job_id}", json={"version": 2})

    assert respuesta.status_code == 204
    elecciones = (config.directorio_salidas / "elecciones.csv").read_text(encoding="utf-8").splitlines()
    ultima = elecciones[-1].split(",")
    assert ultima[1] == job_id and ultima[2] == versiones[1]["estilo"] and ultima[4] == "2"

    # Completar usa el análisis, nunca repite basic-pitch. Un segundo clic
    # y un reinicio del registro siguen devolviendo la misma canción guardada.
    from unittest.mock import patch

    with patch("app.nucleo.extraer_melodia", side_effect=AssertionError("No repetir IA")):
        respuesta = client.post(f"/demo/completa/{job_id}", json={"version": 2})
        assert respuesta.status_code == 202
        completa = respuesta.json()["jobId"]
        assert client.get(f"/demo/archivo/{completa}/cancion-2.mp3").status_code == 200
        with patch("app.nucleo._generar_version", side_effect=AssertionError("No repetir render")):
            trabajos.clear()
            repetida = client.post(f"/demo/completa/{job_id}", json={"version": 2})
            assert repetida.status_code == 200 and repetida.json()["cache"] is True
            assert repetida.json()["jobId"] == completa


def test_eleccion_de_una_version_inexistente_da_error(client):
    assert client.post(f"/demo/eleccion/{uuid4()}", json={"version": 1}).status_code == 404
