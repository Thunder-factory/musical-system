"""
Fixtures compartidas.

Los 3 audios inválidos (silencio, ruido, corto) se generan con ffmpeg en
tiempo de test en vez de versionarse como archivos — mismo patrón que ya
usa probar_entorno.py con melodia_prueba.wav. `mi_tarareo.wav` sí está
versionado en tests/audio/ porque es el caso real contra el que se
midieron las reglas de limpieza (ver CLAUDE.md).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def pytest_configure(config: pytest.Config) -> None:
    # Los jobs de test_main.py (t-completo, t-latencia, ...) escribían en la
    # carpeta salidas/ real del proyecto. Se redirige a una carpeta temporal
    # antes de que app.main lea (y cachee) la configuración; el uvicorn de
    # servidor_en_vivo hereda la variable de entorno.
    os.environ.setdefault("TARAREO_DIRECTORIO_SALIDAS", tempfile.mkdtemp(prefix="tarareo-tests-"))
    # Los tests usan rutas locales en inputUrls, que solo se aceptan en modo
    # desarrollo. Los tests que verifican el rechazo en producción crean su
    # propia Configuracion(modo_desarrollo=False).
    os.environ.setdefault("TARAREO_MODO_DESARROLLO", "true")
    config.addinivalue_line(
        "markers", "slow: corre basic-pitch de verdad (varios segundos por test)"
    )


def _generar_con_ffmpeg(filtro_lavfi: str, destino: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", filtro_lavfi, "-y", str(destino)],
        check=True,
    )
    return destino


@pytest.fixture(scope="session")
def audio_real() -> Path:
    ruta = RAIZ / "tests" / "audio" / "mi_tarareo.wav"
    if not ruta.exists():
        pytest.skip(f"Falta el fixture de audio real: {ruta}")
    return ruta


@pytest.fixture(scope="session")
def audio_silencio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """10s de silencio digital puro -> debe fallar con MotivoFallo.SIN_SENAL."""
    destino = tmp_path_factory.mktemp("fixtures") / "silencio.wav"
    return _generar_con_ffmpeg("anullsrc=r=22050:cl=mono:d=10", destino)


@pytest.fixture(scope="session")
def audio_ruido(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """10s de ruido blanco -> tiene señal (pasa preprocesado) pero sin tono (falla en melodia.py)."""
    destino = tmp_path_factory.mktemp("fixtures") / "ruido.wav"
    # Semilla fija: sin ella el test era inestable. La 4 es justamente el caso
    # difícil (2 notas con confianza 0.437, por encima del umbral de 0.42).
    return _generar_con_ffmpeg("anoisesrc=r=22050:d=10:c=white:seed=4", destino)


@pytest.fixture(scope="session")
def audio_mp3(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Tono corto en mp3, solo para probar que ingesta.py acepta el formato."""
    destino = tmp_path_factory.mktemp("fixtures") / "prueba.mp3"
    return _generar_con_ffmpeg("sine=frequency=440:duration=2", destino)


@pytest.fixture(scope="session")
def audio_webm(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Tono corto en webm/opus (formato típico de MediaRecorder en Chrome/Android)."""
    destino = tmp_path_factory.mktemp("fixtures") / "prueba.webm"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:a", "libopus", "-y", str(destino)],
        check=True,
    )
    return destino


@pytest.fixture(scope="session")
def audio_corto(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """3s de tono puro -> debe fallar con MotivoFallo.GRABACION_MUY_CORTA (< 8s)."""
    destino = tmp_path_factory.mktemp("fixtures") / "corto.wav"
    return _generar_con_ffmpeg("sine=frequency=440:duration=3:sample_rate=22050", destino)


@pytest.fixture(scope="session")
def audio_corto_con_silencio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """10s de archivo: 4s de tono + 6s de silencio -> GRABACION_MUY_CORTA tras recortar."""
    destino = tmp_path_factory.mktemp("fixtures") / "corto_con_silencio.wav"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error",
         "-f", "lavfi", "-i", "sine=frequency=220:duration=4:sample_rate=22050",
         "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono:d=6",
         "-filter_complex", "[0][1]concat=n=2:v=0:a=1", "-ac", "1", "-y", str(destino)],
        check=True,
    )
    return destino


@pytest.fixture
def config():
    """Instancia fresca de Configuracion (no la cacheada de obtener_configuracion)."""
    from app.config import Configuracion

    return Configuracion()


@pytest.fixture(scope="session")
def requiere_render():
    """
    Saltea el test si esta máquina no tiene FluidSynth + SoundFont (etapa 8).
    En desarrollo están en herramientas/ (ver CLAUDE.md); en Docker, por
    TARAREO_FLUIDSYNTH / TARAREO_SOUNDFONT.
    """
    from app.config import Configuracion
    from app.pipeline.render import herramientas_disponibles

    if not herramientas_disponibles(Configuracion()):
        pytest.skip("FluidSynth o el SoundFont no están disponibles en esta máquina")


@pytest.fixture
def directorio_trabajo(tmp_path: Path) -> Path:
    return tmp_path / "job"


@pytest.fixture(scope="session")
def servidor_archivos():
    """
    Servidor HTTP local que hace de "R2" para probar descargas.

    - GET /archivo/<nombre>   devuelve el archivo con Content-Length
    - GET /sin-largo/<nombre> lo devuelve sin Content-Length (el worker
      tiene que cortar igual si supera el máximo)
    - cualquier otra ruta     404, como una URL prefirmada vencida

    Ignora la query string, igual que la firma de una URL prefirmada no
    cambia qué archivo se baja. Devuelve (url_base, carpeta) y los tests
    dejan sus archivos en `carpeta`.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    carpeta = Path(tempfile.mkdtemp(prefix="tarareo-r2-falso-"))

    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            ruta = self.path.split("?", 1)[0]
            prefijo, _, nombre = ruta.lstrip("/").partition("/")
            archivo = carpeta / nombre
            if prefijo not in ("archivo", "sin-largo") or not nombre or not archivo.is_file():
                self.send_error(404)
                return
            datos = archivo.read_bytes()
            self.send_response(200)
            if prefijo == "archivo":
                self.send_header("Content-Length", str(len(datos)))
            else:
                self.close_connection = True
            self.end_headers()
            self.wfile.write(datos)

        def log_message(self, *_args) -> None:
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_address[1]}", carpeta
    finally:
        servidor.shutdown()


class R2Falso:
    """
    Estado del servidor falso de `servidor_r2`. Rutas:

    - PUT  /bucket/<clave>     guarda el cuerpo y el Content-Type en `objetos`
    - GET  /bucket/<clave>     devuelve lo guardado (o un archivo de `carpeta`)
    - POST /callback           guarda (json, headers) en `callbacks`
    - `fallas[clave] = [500, 403...]`: las próximas respuestas a esa clave
      (PUT o callback) son esos códigos, en orden; después responde bien.
    """

    def __init__(self, url_base: str, carpeta: Path) -> None:
        self.url_base = url_base
        self.carpeta = carpeta
        self.objetos: dict[str, tuple[bytes, str]] = {}
        self.callbacks: list[tuple[dict, dict]] = []
        self.fallas: dict[str, list[int]] = {}

    def url_put(self, clave: str) -> str:
        return f"{self.url_base}/bucket/{clave}?X-Amz-Signature=FIRMA-SECRETA&X-Amz-Expires=3600"

    def limpiar(self) -> None:
        self.objetos.clear()
        self.callbacks.clear()
        self.fallas.clear()


@pytest.fixture(scope="session")
def _r2_sesion():
    import json as json_
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    carpeta = Path(tempfile.mkdtemp(prefix="tarareo-r2-"))
    estado: dict[str, R2Falso] = {}

    class Manejador(BaseHTTPRequestHandler):
        def _clave(self) -> str:
            return self.path.split("?", 1)[0].removeprefix("/bucket/")

        def _falla_pendiente(self, clave: str) -> int | None:
            pendientes = estado["r2"].fallas.get(clave)
            return pendientes.pop(0) if pendientes else None

        def _responder(self, codigo: int, cuerpo: bytes = b"") -> None:
            self.send_response(codigo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_PUT(self) -> None:
            clave = self._clave()
            datos = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            falla = self._falla_pendiente(clave)
            if falla:
                self._responder(falla)
                return
            estado["r2"].objetos[clave] = (datos, self.headers.get("Content-Type", ""))
            self._responder(200)

        def do_GET(self) -> None:
            clave = self._clave()
            if clave in estado["r2"].objetos:
                self._responder(200, estado["r2"].objetos[clave][0])
            elif (carpeta / clave).is_file():
                self._responder(200, (carpeta / clave).read_bytes())
            else:
                self._responder(404)

        def do_POST(self) -> None:
            datos = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            falla = self._falla_pendiente("callback")
            if falla:
                self._responder(falla)
                return
            estado["r2"].callbacks.append((json_.loads(datos), dict(self.headers)))
            self._responder(200)

        def log_message(self, *_args) -> None:
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    estado["r2"] = R2Falso(f"http://127.0.0.1:{servidor.server_address[1]}", carpeta)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        yield estado["r2"]
    finally:
        servidor.shutdown()


@pytest.fixture
def servidor_r2(_r2_sesion):
    """R2 falso (ver `R2Falso`), limpio en cada test."""
    _r2_sesion.limpiar()
    return _r2_sesion


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor_en_vivo():
    """
    Levanta uvicorn de verdad en un subproceso.

    Existe solo para el test de latencia de POST /procesar: con
    TestClient (usado en el resto de test_main.py) los BackgroundTasks se
    ejecutan de forma síncrona antes de que .post() devuelva el control,
    así que medir tiempos ahí daría el tiempo del pipeline completo
    (~30s), no el de la respuesta HTTP real.
    """
    import httpx

    puerto = _puerto_libre()
    proceso = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(puerto), "--log-level", "warning"],
        cwd=RAIZ,
    )
    base_url = f"http://127.0.0.1:{puerto}"
    try:
        # Hasta 60 s: ahora el servidor carga el modelo de basic-pitch
        # (importa TensorFlow) ANTES de responder la primera solicitud.
        for _ in range(300):
            try:
                if httpx.get(f"{base_url}/salud", timeout=1.0).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            import time
            time.sleep(0.2)
        else:
            proceso.terminate()
            pytest.fail("El servidor uvicorn de prueba no respondió a tiempo")

        yield base_url
    finally:
        proceso.terminate()
        proceso.wait(timeout=10)
