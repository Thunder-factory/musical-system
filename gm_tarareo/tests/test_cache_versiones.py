from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.capacidad import ControlCapacidad
from app.config import Configuracion
from app.demo import crear_router
from app.modelos import EstadoJob, RespuestaProcesar, ResultadoJob


@pytest.fixture
def demo_cache(tmp_path, monkeypatch):
    config = Configuracion(directorio_salidas=tmp_path)
    cap = ControlCapacidad(2)
    llamadas, registro = [], {}
    monkeypatch.setattr("app.demo.analisis_guardado", lambda *_: SimpleNamespace(
        versiones=[SimpleNamespace(numero=1), SimpleNamespace(numero=2)]))

    async def despachar(solicitud, _tareas):
        llamadas.append(solicitud)
        registro[solicitud.jobId] = ResultadoJob(jobId=solicitud.jobId, estado=EstadoJob.PROCESANDO, progreso=0)
        return RespuestaProcesar(jobId=solicitud.jobId)

    app = FastAPI()
    app.include_router(crear_router(despachar, config, registro.get, cap))
    with TestClient(app) as client:
        yield client, llamadas, cap


def test_dos_clics_sobre_una_version_en_proceso_no_crean_dos_jobs(demo_cache):
    client, llamadas, _ = demo_cache
    origen = uuid4()
    uno = client.post(f"/demo/completa/{origen}", json={"version": 2})
    dos = client.post(f"/demo/completa/{origen}", json={"version": 2})
    assert uno.status_code == dos.status_code == 202
    assert uno.json()["jobId"] == dos.json()["jobId"]
    assert len(llamadas) == 1 and llamadas[0].operacion == "completar"


def test_no_se_anticipa_si_hay_trabajo_y_la_peticion_expresa_si_se_admite(demo_cache):
    client, llamadas, cap = demo_cache
    cap.intentar_ocupar()
    origen = uuid4()
    assert client.post(f"/demo/completa/{origen}", json={"version": 1, "anticipar": True}).status_code == 503
    assert not llamadas
    assert client.post(f"/demo/completa/{origen}", json={"version": 1}).status_code == 202


def test_no_se_pueden_pedir_estilos_que_no_se_ofrecieron(demo_cache):
    client, llamadas, _ = demo_cache
    assert client.post(f"/demo/completa/{uuid4()}", json={"version": 3}).status_code == 422
    assert not llamadas
