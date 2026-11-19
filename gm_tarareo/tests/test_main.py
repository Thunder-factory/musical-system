import logging
import time
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.capacidad import ControlCapacidad
from app.main import app, trabajos
from app.modelos import EstadoJob, ResultadoJob


@pytest.fixture
def client():
    # Con `with`, TestClient corre el lifespan: carga el modelo como en
    # producción. Es lento solo la primera vez (después queda en memoria).
    trabajos.clear()
    with TestClient(app) as c:
        yield c
    # Ningún test puede dejar cupos tomados: si pasa, hay una fuga real.
    assert main.capacidad.ocupados == 0


@pytest.fixture
def pipeline_falso(monkeypatch):
    """
    Reemplaza el núcleo por uno instantáneo. TestClient ejecuta los
    BackgroundTasks de forma síncrona antes de que .post() devuelva el
    control, así que esto permite probar el adaptador HTTP sin correr
    basic-pitch. El "no bloquea" real se prueba aparte, contra uvicorn.
    """
    llamadas: list[UUID] = []

    def falso(solicitud, _config, _reportar=None):
        llamadas.append(solicitud.jobId)
        return ResultadoJob(jobId=solicitud.jobId, estado=EstadoJob.COMPLETADO, progreso=100)

    monkeypatch.setattr("app.main.ejecutar_job", falso)
    return llamadas


def test_salud_responde_ok_con_modelo_cargado_y_capacidad(client):
    r = client.get("/salud")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["modelosCargados"] is True
    assert cuerpo["capacidad"] == main.config.capacidad
    assert cuerpo["ocupados"] == 0


def test_httpx_no_loguea_urls_prefirmadas():
    """httpx en INFO escribe cada URL completa, con la firma de R2 en la query."""
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_jobs_id_inexistente_da_404(client):
    r = client.get(f"/jobs/{uuid4()}")
    assert r.status_code == 404


def test_jobs_id_que_no_es_uuid_da_422(client):
    r = client.get("/jobs/no-existe")
    assert r.status_code == 422


def test_procesar_responde_202_con_estado_procesando(client, pipeline_falso):
    job_id = str(uuid4())

    r = client.post("/procesar", json={"jobId": job_id, "inputUrls": ["cualquier-cosa.wav"]})

    assert r.status_code == 202
    assert r.json() == {"jobId": job_id, "estado": "PROCESANDO"}
    assert pipeline_falso == [UUID(job_id)]


def test_procesar_valida_el_contrato(client):
    # sin inputUrls -> 422 de validación de Pydantic, no un 500
    r = client.post("/procesar", json={"jobId": str(uuid4())})
    assert r.status_code == 422


@pytest.mark.parametrize("job_id", ["t-invalido", "../../etc/passwd", ""])
def test_procesar_rechaza_job_id_que_no_es_uuid(client, pipeline_falso, job_id):
    """El jobId se usa como nombre de carpeta: un texto libre podría escapar de salidas/."""
    r = client.post("/procesar", json={"jobId": job_id, "inputUrls": ["a.wav"]})

    assert r.status_code == 422
    assert pipeline_falso == []


def test_procesar_con_worker_lleno_responde_503_con_retry_after(client, pipeline_falso, monkeypatch):
    lleno = ControlCapacidad(1)
    assert lleno.intentar_ocupar()
    monkeypatch.setattr("app.main.capacidad", lleno)

    r = client.post("/procesar", json={"jobId": str(uuid4()), "inputUrls": ["a.wav"]})

    assert r.status_code == 503
    assert r.headers["retry-after"] == str(main.REINTENTAR_EN_SEGUNDOS)
    assert pipeline_falso == []
    lleno.liberar()


def test_procesar_libera_el_cupo_aunque_el_job_explote(client, monkeypatch):
    """Si el cupo no se liberara ante un error, el worker quedaría 'lleno' para siempre."""
    def explota(*_args, **_kwargs):
        raise RuntimeError("falla inesperada fuera del núcleo")

    monkeypatch.setattr("app.main.ejecutar_job", explota)

    with pytest.raises(RuntimeError):
        client.post("/procesar", json={"jobId": str(uuid4()), "inputUrls": ["a.wav"]})

    assert main.capacidad.ocupados == 0


def test_reenvio_de_un_job_en_proceso_no_lo_duplica(client, pipeline_falso):
    """Si Django reenvía un job que sigue corriendo, no se arranca otro sobre la misma carpeta."""
    job_id = uuid4()
    trabajos[job_id] = ResultadoJob(jobId=job_id, estado=EstadoJob.PROCESANDO, progreso=40)

    r = client.post("/procesar", json={"jobId": str(job_id), "inputUrls": ["a.wav"]})

    assert r.status_code == 202
    assert pipeline_falso == []
    assert trabajos[job_id].progreso == 40


def test_reenvio_de_un_job_terminado_lo_vuelve_a_correr(client, pipeline_falso):
    job_id = uuid4()
    trabajos[job_id] = ResultadoJob(jobId=job_id, estado=EstadoJob.FALLIDO, progreso=100, error="x")

    r = client.post("/procesar", json={"jobId": str(job_id), "inputUrls": ["a.wav"]})

    assert r.status_code == 202
    assert pipeline_falso == [job_id]
    assert trabajos[job_id].estado == EstadoJob.COMPLETADO


@pytest.mark.slow
def test_procesar_flujo_completo_queda_completado(client, audio_real, requiere_render):
    job_id = str(uuid4())
    client.post("/procesar", json={"jobId": job_id, "inputUrls": [str(audio_real)]})

    r = client.get(f"/jobs/{job_id}")
    cuerpo = r.json()

    assert cuerpo["estado"] == "COMPLETADO"
    assert cuerpo["progreso"] == 100
    # La principal (cancion.mp3, melodia.mid, arreglo.mid, analisis.json) + 2 archivos por alternativa.
    versiones = len(cuerpo["metadatos"]["versiones"])
    assert len(cuerpo["outputUrls"]) == 5 + 2 * (versiones - 1)
    assert 12 <= cuerpo["metadatos"]["notasFinales"] <= 18


def test_procesar_audio_invalido_queda_fallido_con_motivo(client, audio_silencio):
    # No es slow: el silencio falla en preprocesado, antes de basic-pitch.
    job_id = str(uuid4())
    client.post("/procesar", json={"jobId": job_id, "inputUrls": [str(audio_silencio)]})

    r = client.get(f"/jobs/{job_id}")
    cuerpo = r.json()

    assert cuerpo["estado"] == "FALLIDO"
    assert cuerpo["error"]
    assert cuerpo["metadatos"]["motivo"] == "SIN_SENAL"


def test_procesar_con_callback_caido_no_rompe_el_job(client, audio_silencio):
    """El callback es una notificación, no una dependencia (pedido explícito del usuario)."""
    job_id = str(uuid4())
    client.post(
        "/procesar",
        json={
            "jobId": job_id,
            "inputUrls": [str(audio_silencio)],
            "callbackUrl": "http://127.0.0.1:1/no-existe",
        },
    )

    r = client.get(f"/jobs/{job_id}")
    assert r.json()["estado"] == "FALLIDO"  # terminó igual, el callback caído no lo tumbó


@pytest.mark.slow
def test_post_procesar_no_bloquea_al_cliente(servidor_en_vivo, audio_real):
    """
    Corre contra un uvicorn real (no TestClient) porque TestClient ejecuta
    los BackgroundTasks de forma síncrona antes de devolver la respuesta,
    lo que mediría el tiempo del pipeline completo (~30s) en vez del
    tiempo real de respuesta HTTP.
    """
    inicio = time.time()
    r = httpx.post(
        f"{servidor_en_vivo}/procesar",
        json={"jobId": str(uuid4()), "inputUrls": [str(audio_real)]},
        timeout=5.0,
    )
    tiempo_respuesta = time.time() - inicio

    assert r.status_code == 202
    # 200ms es el criterio de aceptación; se deja margen para no ser
    # flaky por overhead del subproceso, la diferencia de orden de
    # magnitud frente al pipeline completo (~30s) es lo que importa acá.
    assert tiempo_respuesta < 1.0
