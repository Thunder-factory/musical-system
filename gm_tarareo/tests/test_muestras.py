from pathlib import Path
from uuid import uuid4

from app.config import Configuracion
from app.modelos import CodigoError, SolicitudProcesar
from app.nucleo import ejecutar_job
from app.pipeline.muestras import recortar_muestra
from app.versiones import identificador_version
from tests.test_render import _arreglo_de_prueba


def test_muestra_toma_la_melodia_sin_intro_y_no_toda_la_cancion(config):
    arreglo = _arreglo_de_prueba(config)
    muestra = recortar_muestra(arreglo, 16)
    assert muestra.arreglo.duracionSegundos == 16
    assert any(e.pista == "melodia" and e.inicio < 1 for e in muestra.eventos)
    assert min(e.inicio for e in muestra.eventos) >= 0
    assert max(e.inicio + e.duracion for e in muestra.eventos) <= 16 * arreglo.arreglo.bpm / 60 + 1e-6
    assert len(muestra.eventos) < len(arreglo.eventos)


def test_cache_identifica_tarareo_version_y_ajustes_de_sonido(config):
    origen = uuid4()
    a = identificador_version(origen, 1, config)
    assert a == identificador_version(origen, 1, config)
    assert a != identificador_version(origen, 2, config)
    assert a != identificador_version(origen, 1, config.model_copy(update={"render_masterizacion": False}))


def test_completar_un_analisis_invalido_falla_sin_repetir_ia(tmp_path, monkeypatch):
    ruta = tmp_path / "analisis.json"
    ruta.write_text("{}")
    monkeypatch.setattr("app.nucleo.extraer_melodia", lambda *_: (_ for _ in ()).throw(AssertionError("No repetir IA")))
    resultado = ejecutar_job(SolicitudProcesar(jobId=uuid4(), inputUrls=[str(ruta)], operacion="completar"),
                             Configuracion(modo_desarrollo=True, directorio_salidas=tmp_path))
    assert resultado.codigoError == CodigoError.ENTRADA_INVALIDA
    assert not list(Path(tmp_path).glob("*/cancion*.mp3"))
