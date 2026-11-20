"""
Tests del bloque 2 (integración con Django y R2) y de la deuda técnica 4.

Contra un R2 falso (`servidor_r2` en conftest.py) que guarda lo que se sube,
registra los callbacks y puede simular fallas.
"""

import json
import time
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.almacenamiento import subir_salidas
from app.config import Configuracion
from app.modelos import (
    TIPOS_SALIDA,
    CodigoError,
    EstadoJob,
    ResultadoJob,
    SolicitudProcesar,
)
from app.nucleo import ejecutar_job
from app.pipeline.excepciones import ErrorAlmacenamiento
from app.reintentos import con_reintentos
from app.retencion import RegistroJobs, purgar_salidas


@pytest.mark.slow
def test_completa_una_muestra_guardada_en_r2_sin_repetir_la_ia(servidor_r2, audio_real, config,
                                                           requiere_render, monkeypatch):
    (servidor_r2.carpeta / "entrada.wav").write_bytes(audio_real.read_bytes())
    origen = uuid4()
    urls = {n: servidor_r2.url_put(f"muestras/{origen}/{n}") for n in TIPOS_SALIDA}
    muestras = ejecutar_job(SolicitudProcesar(
        jobId=origen, inputUrls=[f"{servidor_r2.url_base}/bucket/entrada.wav"],
        operacion="muestras", outputUploadUrls=urls,
    ), config)
    assert muestras.estado == EstadoJob.COMPLETADO, muestras.error
    guardado = json.loads(servidor_r2.objetos[f"muestras/{origen}/analisis.json"][0])
    assert all(v["tipo"] == "muestra" and v["duracionSegundos"] < 21 for v in guardado["versiones"])
    assert f"muestras/{origen}/partitura.musicxml" in servidor_r2.objetos

    def no_repetir(*_args):
        raise AssertionError("Completar no debe volver a extraer notas")

    monkeypatch.setattr("app.nucleo.extraer_melodia", no_repetir)
    nuevo = uuid4()
    completa = ejecutar_job(SolicitudProcesar(
        jobId=nuevo, operacion="completar", versionElegida=2,
        inputUrls=[f"{servidor_r2.url_base}/bucket/muestras/{origen}/analisis.json"],
        outputUploadUrls={n: servidor_r2.url_put(f"completas/{nuevo}/{n}")
                          for n in ("cancion-2.mp3", "arreglo-2.mid", "partitura.musicxml", "analisis.json")},
    ), config)
    assert completa.estado == EstadoJob.COMPLETADO, completa.error
    assert completa.metadatos["versiones"][0]["tipo"] == "completa"
    assert completa.metadatos["duracionCancionSegundos"] > 55
    assert not config.directorio_job(origen).exists() and not config.directorio_job(nuevo).exists()


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    """Los reintentos esperan 1 s, 2 s, 4 s: en los tests no hace falta esperar."""
    monkeypatch.setattr("app.reintentos.time.sleep", lambda _s: None)


# --- Reintentos ------------------------------------------------------------

def _error_http(codigo: int) -> httpx.HTTPStatusError:
    pedido = httpx.Request("PUT", "http://r2/x")
    return httpx.HTTPStatusError("x", request=pedido, response=httpx.Response(codigo, request=pedido))


def test_reintenta_errores_transitorios_hasta_que_sale_bien():
    intentos = []

    def operacion():
        intentos.append(1)
        if len(intentos) < 3:
            raise _error_http(503)
        return "ok"

    assert con_reintentos(operacion, reintentos=3, que="prueba") == "ok"
    assert len(intentos) == 3


def test_no_reintenta_un_4xx():
    """Un 403 (URL vencida, firma inválida) no se arregla repitiendo."""
    intentos = []

    def operacion():
        intentos.append(1)
        raise _error_http(403)

    with pytest.raises(httpx.HTTPStatusError):
        con_reintentos(operacion, reintentos=3, que="prueba")
    assert len(intentos) == 1


def test_se_rinde_despues_de_los_reintentos():
    intentos = []

    def operacion():
        intentos.append(1)
        raise httpx.ConnectError("sin red")

    with pytest.raises(httpx.ConnectError):
        con_reintentos(operacion, reintentos=2, que="prueba")
    assert len(intentos) == 3  # el intento original + 2 reintentos


# --- Subida a R2 -------------------------------------------------------------

def _archivos_de_prueba(tmp_path):
    archivos = {}
    for nombre, contenido in [("cancion.mp3", b"ID3 mp3 falso"), ("melodia.mid", b"MThd"),
                              ("arreglo.mid", b"MThd arreglo"), ("analisis.json", b'{"bpm": 64}')]:
        ruta = tmp_path / nombre
        ruta.write_bytes(contenido)
        archivos[nombre] = ruta
    return archivos


def test_sube_cada_salida_con_su_content_type_y_devuelve_urls_sin_firma(servidor_r2, tmp_path, config):
    archivos = _archivos_de_prueba(tmp_path)
    urls = {nombre: servidor_r2.url_put(f"jobs/abc/{nombre}") for nombre in archivos}

    subidas = subir_salidas(archivos, urls, config)

    assert servidor_r2.objetos["jobs/abc/cancion.mp3"] == (b"ID3 mp3 falso", "audio/mpeg")
    assert servidor_r2.objetos["jobs/abc/melodia.mid"][1] == "audio/midi"
    assert servidor_r2.objetos["jobs/abc/analisis.json"][1] == "application/json"
    assert all("FIRMA-SECRETA" not in u for u in subidas)
    assert subidas[0] == f"{servidor_r2.url_base}/bucket/jobs/abc/cancion.mp3"


def test_django_puede_pedir_solo_algunas_salidas(servidor_r2, tmp_path, config):
    archivos = _archivos_de_prueba(tmp_path)
    subir_salidas(archivos, {"cancion.mp3": servidor_r2.url_put("solo/cancion.mp3")}, config)
    assert list(servidor_r2.objetos) == ["solo/cancion.mp3"]


def test_un_500_momentaneo_de_r2_se_reintenta(servidor_r2, tmp_path, config):
    servidor_r2.fallas["x/cancion.mp3"] = [500]
    archivos = _archivos_de_prueba(tmp_path)

    subir_salidas(archivos, {"cancion.mp3": servidor_r2.url_put("x/cancion.mp3")}, config)

    assert "x/cancion.mp3" in servidor_r2.objetos


def test_url_vencida_da_error_reintentable_sin_exponer_la_firma(servidor_r2, tmp_path, config):
    servidor_r2.fallas["x/cancion.mp3"] = [403]
    archivos = _archivos_de_prueba(tmp_path)

    with pytest.raises(ErrorAlmacenamiento) as info:
        subir_salidas(archivos, {"cancion.mp3": servidor_r2.url_put("x/cancion.mp3")}, config)

    assert info.value.codigo == CodigoError.ERROR_INTERNO  # Django firma URLs nuevas y reintenta
    assert "403" in info.value.mensaje and "vencida" in info.value.mensaje
    assert "FIRMA-SECRETA" not in info.value.mensaje


# --- Contrato ------------------------------------------------------------------

def test_contrato_rechaza_salidas_desconocidas():
    with pytest.raises(ValueError, match="desconocidas"):
        SolicitudProcesar(jobId=uuid4(), inputUrls=["http://x/a.m4a"], outputUploadUrls={"video.mp4": "http://x"})


def test_contrato_rechaza_otra_version():
    with pytest.raises(ValueError):
        SolicitudProcesar(jobId=uuid4(), version=2, inputUrls=["http://x/a.m4a"])


def test_genero_ya_no_esta_en_el_contrato_pero_se_acepta_y_se_ignora():
    solicitud = SolicitudProcesar(jobId=uuid4(), inputUrls=["http://x/a.m4a"], parametros={"genero": "rock"})
    assert "genero" not in type(solicitud.parametros).model_fields
    assert solicitud.parametros.model_extra == {"genero": "rock"}


# --- Códigos de error ----------------------------------------------------------

def test_audio_invalido_es_definitivo(audio_silencio, config):
    resultado = ejecutar_job(SolicitudProcesar(jobId=uuid4(), inputUrls=[str(audio_silencio)]), config)
    assert resultado.codigoError == CodigoError.ENTRADA_INVALIDA
    assert resultado.etapa == "preprocesado"


def test_descarga_fallida_es_reintentable(servidor_r2, config):
    url = f"{servidor_r2.url_base}/bucket/no-existe.m4a?X-Amz-Signature=FIRMA-SECRETA"
    resultado = ejecutar_job(SolicitudProcesar(jobId=uuid4(), inputUrls=[url]), config)

    assert resultado.estado == EstadoJob.FALLIDO
    assert resultado.codigoError == CodigoError.ERROR_INTERNO
    assert resultado.etapa == "ingesta"
    assert "FIRMA-SECRETA" not in resultado.error


@pytest.mark.slow
def test_job_completo_sube_todo_a_r2_y_borra_la_copia_local(servidor_r2, audio_real, config, requiere_render):
    job_id = uuid4()
    (servidor_r2.carpeta / "entrada.wav").write_bytes(audio_real.read_bytes())
    claves = {n: f"jobs/{job_id}/{n}" for n in ("cancion.mp3", "melodia.mid", "arreglo.mid", "analisis.json")}
    solicitud = SolicitudProcesar(
        jobId=job_id,
        inputUrls=[f"{servidor_r2.url_base}/bucket/entrada.wav?X-Amz-Signature=FIRMA-SECRETA"],
        outputUploadUrls={n: servidor_r2.url_put(c) for n, c in claves.items()},
    )
    etapas = []

    resultado = ejecutar_job(solicitud, config, lambda _p, e, *_: etapas.append(e))

    assert resultado.estado == EstadoJob.COMPLETADO
    assert "version-1-lista" in etapas
    assert set(servidor_r2.objetos) == set(claves.values())
    assert servidor_r2.objetos[claves["cancion.mp3"]][0][:3] in (b"ID3", b"\xff\xfb")  # es un MP3
    assert resultado.outputUrls == [f"{servidor_r2.url_base}/bucket/{c}" for c in claves.values()]
    assert not config.directorio_job(job_id).exists()  # la copia local se borró


# --- Callbacks: progreso, token y reintento --------------------------------------

@pytest.fixture
def client_con_token(monkeypatch):
    monkeypatch.setattr(main.config, "callback_token", Configuracion(callback_token="secreto-compartido").callback_token)
    main.trabajos.clear()
    with TestClient(main.app) as c:
        yield c


def test_callbacks_de_progreso_y_final_con_token(client_con_token, servidor_r2, monkeypatch):
    def falso(solicitud, _config, reportar):
        reportar(20, "melodia")
        reportar(82, "render")
        return ResultadoJob(jobId=solicitud.jobId, estado=EstadoJob.COMPLETADO, progreso=100, etapa="completado")

    monkeypatch.setattr("app.main.ejecutar_job", falso)
    job_id = str(uuid4())

    client_con_token.post("/procesar", json={
        "jobId": job_id, "inputUrls": ["a.wav"], "callbackUrl": f"{servidor_r2.url_base}/callback",
    })

    cuerpos = [c[0] for c in servidor_r2.callbacks]
    assert [(c["estado"], c["progreso"], c["etapa"]) for c in cuerpos] == [
        ("PROCESANDO", 20, "melodia"), ("PROCESANDO", 82, "render"), ("COMPLETADO", 100, "completado"),
    ]
    assert all(h.get("X-Worker-Token") == "secreto-compartido" for _, h in servidor_r2.callbacks)


def test_el_callback_final_se_reintenta_si_django_falla(client_con_token, servidor_r2, monkeypatch):
    monkeypatch.setattr("app.main.ejecutar_job", lambda s, _c, _r: ResultadoJob(
        jobId=s.jobId, estado=EstadoJob.COMPLETADO, progreso=100))
    servidor_r2.fallas["callback"] = [502, 503]

    client_con_token.post("/procesar", json={
        "jobId": str(uuid4()), "inputUrls": ["a.wav"], "callbackUrl": f"{servidor_r2.url_base}/callback",
    })

    assert [c[0]["estado"] for c in servidor_r2.callbacks] == ["COMPLETADO"]


def test_el_token_no_aparece_en_los_logs(client_con_token, servidor_r2, monkeypatch, caplog):
    monkeypatch.setattr("app.main.ejecutar_job", lambda s, _c, _r: ResultadoJob(
        jobId=s.jobId, estado=EstadoJob.COMPLETADO, progreso=100))
    servidor_r2.fallas["callback"] = [500] * 10  # que falle todo y loguee el error

    with caplog.at_level("INFO"):
        client_con_token.post("/procesar", json={
            "jobId": str(uuid4()), "inputUrls": ["a.wav"], "callbackUrl": f"{servidor_r2.url_base}/callback",
        })

    assert "secreto-compartido" not in caplog.text
    assert "No se pudo notificar el callback" in caplog.text


# --- Retención (deuda técnica 4) ----------------------------------------------

class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _resultado(estado=EstadoJob.COMPLETADO):
    return ResultadoJob(jobId=uuid4(), estado=estado, progreso=100 if estado != EstadoJob.PROCESANDO else 0)


def test_los_jobs_terminados_se_olvidan_despues_de_la_retencion():
    reloj = Reloj()
    registro = RegistroJobs(retencion_segundos=60, maximo=100, reloj=reloj)
    viejo = _resultado()
    registro[viejo.jobId] = viejo

    reloj.t = 61
    nuevo = _resultado()
    registro[nuevo.jobId] = nuevo

    assert registro.get(viejo.jobId) is None
    assert registro.get(nuevo.jobId) is not None


def test_nunca_hay_mas_jobs_terminados_que_el_maximo():
    registro = RegistroJobs(retencion_segundos=3600, maximo=5, reloj=Reloj())
    for _ in range(20):
        r = _resultado()
        registro[r.jobId] = r
    assert len(registro) == 5


def test_un_job_en_proceso_nunca_se_olvida():
    reloj = Reloj()
    registro = RegistroJobs(retencion_segundos=60, maximo=1, reloj=reloj)
    en_curso = _resultado(EstadoJob.PROCESANDO)
    registro[en_curso.jobId] = en_curso
    reloj.t = 10_000
    for _ in range(5):
        r = _resultado()
        registro[r.jobId] = r

    assert registro.get(en_curso.jobId) is not None
    assert registro.en_proceso() == {en_curso.jobId}


def test_purga_carpetas_viejas_y_respeta_las_en_proceso(tmp_path):
    vieja, reciente, en_proceso = (tmp_path / n for n in ("vieja", "reciente", "en-proceso"))
    for carpeta in (vieja, reciente, en_proceso):
        carpeta.mkdir()
        (carpeta / "cancion.mp3").write_bytes(b"x")
    ahora = time.time()
    import os
    os.utime(vieja, (ahora - 48 * 3600, ahora - 48 * 3600))
    os.utime(en_proceso, (ahora - 48 * 3600, ahora - 48 * 3600))

    borradas = purgar_salidas(tmp_path, retencion_horas=24, en_proceso={"en-proceso"}, ahora=ahora)

    assert borradas == 1
    assert not vieja.exists() and reciente.exists() and en_proceso.exists()
