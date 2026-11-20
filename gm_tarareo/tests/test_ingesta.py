import shutil
from pathlib import Path

import pytest

from app.config import Configuracion
from app.pipeline.excepciones import ErrorIngesta
from app.pipeline.ingesta import describir_url, ingestar, obtener_archivo_local


def test_ingestar_wav_real_produce_wav_valido(audio_real, directorio_trabajo):
    resultado = ingestar(audio_real, directorio_trabajo, 22050)

    assert resultado.exists()
    assert resultado.suffix == ".wav"
    assert resultado.stat().st_size > 0


def test_ingestar_acepta_m4a(directorio_trabajo):
    # Grabación original de iPhone (m4a/aac); mi_tarareo.wav es su conversión.
    m4a = Path(__file__).resolve().parent / "audio" / "mi_tarareo.m4a"
    if not m4a.exists():
        pytest.skip(f"Falta el fixture de audio real: {m4a}")

    resultado = ingestar(m4a, directorio_trabajo, 22050)
    assert resultado.exists()


def test_ingestar_acepta_mp3(audio_mp3, directorio_trabajo):
    resultado = ingestar(audio_mp3, directorio_trabajo, 22050)
    assert resultado.exists() and resultado.stat().st_size > 0


def test_ingestar_acepta_webm_opus(audio_webm, directorio_trabajo):
    resultado = ingestar(audio_webm, directorio_trabajo, 22050)
    assert resultado.exists() and resultado.stat().st_size > 0


def test_ingestar_archivo_inexistente_lanza_error_claro(directorio_trabajo):
    with pytest.raises(ErrorIngesta, match="no existe"):
        ingestar(Path("no_existe.wav"), directorio_trabajo, 22050)


def test_ingestar_archivo_corrupto_lanza_error_claro(tmp_path, directorio_trabajo):
    basura = tmp_path / "basura.wav"
    basura.write_bytes(b"esto no es un archivo de audio" * 20)

    with pytest.raises(ErrorIngesta):
        ingestar(basura, directorio_trabajo, 22050)


def test_ingestar_archivo_vacio_lanza_error_claro(tmp_path, directorio_trabajo):
    vacio = tmp_path / "vacio.wav"
    vacio.write_bytes(b"")

    with pytest.raises(ErrorIngesta, match="vacío"):
        ingestar(vacio, directorio_trabajo, 22050)


def test_obtener_archivo_local_con_ruta_directa_en_modo_desarrollo(audio_real, tmp_path, config):
    assert config.modo_desarrollo is True  # lo activa conftest.py
    resultado = obtener_archivo_local(str(audio_real), tmp_path, config)
    assert resultado == audio_real


def test_obtener_archivo_local_inexistente_lanza_error(tmp_path, config):
    with pytest.raises(ErrorIngesta):
        obtener_archivo_local("no_existe.wav", tmp_path, config)


@pytest.mark.parametrize("prefijo", ["", "file://"])
def test_ruta_local_se_rechaza_fuera_de_modo_desarrollo(audio_real, tmp_path, prefijo):
    """En producción solo se aceptan URLs: si no, quien llame al worker podría hacerle leer cualquier archivo."""
    config_produccion = Configuracion(modo_desarrollo=False)

    with pytest.raises(ErrorIngesta, match="TARAREO_MODO_DESARROLLO"):
        obtener_archivo_local(prefijo + str(audio_real), tmp_path, config_produccion)


def test_ruta_local_mas_grande_que_el_maximo_se_rechaza(tmp_path):
    grande = tmp_path / "grande.wav"
    grande.write_bytes(b"\0" * 4096)
    config_chica = Configuracion(modo_desarrollo=True, descarga_tamano_maximo_mb=0.001)  # ~1 KB

    with pytest.raises(ErrorIngesta, match="supera el máximo"):
        obtener_archivo_local(str(grande), tmp_path / "job", config_chica)


def test_descarga_http_guarda_el_archivo_en_la_carpeta_del_job(servidor_archivos, audio_real, tmp_path):
    url_base, carpeta = servidor_archivos
    shutil.copy(audio_real, carpeta / "tarareo.wav")
    # Funciona igual fuera de modo desarrollo: es el caso de producción (R2).
    config_produccion = Configuracion(modo_desarrollo=False)

    resultado = obtener_archivo_local(
        f"{url_base}/archivo/tarareo.wav?X-Amz-Signature=abc123", tmp_path, config_produccion
    )

    assert resultado == tmp_path / "entrada.wav"
    assert resultado.read_bytes() == audio_real.read_bytes()


@pytest.mark.parametrize("prefijo", ["archivo", "sin-largo"])
def test_descarga_mas_grande_que_el_maximo_se_corta(servidor_archivos, tmp_path, prefijo):
    """Con Content-Length se rechaza antes de bajar; sin él, al pasar el máximo mientras llega."""
    url_base, carpeta = servidor_archivos
    (carpeta / "enorme.webm").write_bytes(b"\0" * 8192)
    config_chica = Configuracion(descarga_tamano_maximo_mb=0.001)  # ~1 KB

    with pytest.raises(ErrorIngesta, match="supera el máximo"):
        obtener_archivo_local(f"{url_base}/{prefijo}/enorme.webm", tmp_path, config_chica)

    assert not (tmp_path / "entrada.webm").exists()  # no deja el archivo a medias


def test_error_de_descarga_no_expone_la_firma_de_la_url(servidor_archivos, tmp_path, config):
    """La URL prefirmada da acceso al archivo: no puede terminar en el `error` que se le devuelve al backend."""
    url_base, _ = servidor_archivos

    with pytest.raises(ErrorIngesta) as info:
        obtener_archivo_local(f"{url_base}/archivo/no-existe.webm?X-Amz-Signature=secreto", tmp_path, config)

    assert "404" in info.value.mensaje
    assert "secreto" not in info.value.mensaje
    assert "X-Amz-Signature" not in info.value.mensaje


def test_describir_url_quita_la_query_string():
    assert describir_url("https://cuenta.r2.cloudflarestorage.com/b/a.webm?X-Amz-Signature=x") == (
        "https://cuenta.r2.cloudflarestorage.com/b/a.webm"
    )
