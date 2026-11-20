"""
Simulador de Django + R2 para probar el worker de punta a punta, en Docker.

Hace lo que va a hacer el backend real (docs/INTEGRACION-DJANGO.md):
- sirve los tarareos por GET y recibe las salidas por PUT, como R2
  (controla que cada archivo llegue con su Content-Type);
- despacha un job por tarareo con POST /procesar, con outputUploadUrls y
  callbackUrl, y reintenta cuando el worker responde 503 (lleno);
- recibe los callbacks, rechaza los que no traen el token correcto y anota
  el progreso de cada job;
- al final verifica cada resultado y escribe un informe.

Casos que prueba además de los tarareos válidos:
- un tarareo demasiado corto  → FALLIDO, ENTRADA_INVALIDA (no reintentar)
- una URL de entrada vencida  → FALLIDO, ERROR_INTERNO (reintentar)

Solo usa la biblioteca estándar de Python (corre en python:3.11-slim).

    docker compose -f docker-compose.integracion.yml up --build --abort-on-container-exit --exit-code-from simulador
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WORKER = os.environ.get("WORKER_URL", "http://worker-tarareo:8000")
PROPIO = os.environ.get("SIMULADOR_URL", "http://simulador:9000")
TOKEN = os.environ["TOKEN_ESPERADO"]
AUDIOS = Path(os.environ.get("AUDIOS", "/audios"))
RESULTADOS = Path(os.environ.get("RESULTADOS", "/resultados"))
FIRMA = "X-Amz-Signature=firma-de-prueba&X-Amz-Expires=3600"
TIPOS = {"cancion.mp3": "audio/mpeg", "melodia.mid": "audio/midi",
         "arreglo.mid": "audio/midi", "analisis.json": "application/json",
         "partitura.musicxml": "application/vnd.recordare.musicxml+xml",
         "cancion-2.mp3": "audio/mpeg", "arreglo-2.mid": "audio/midi",
         "cancion-3.mp3": "audio/mpeg", "arreglo-3.mid": "audio/midi"}

estado = {"callbacks": [], "rechazados": 0, "subidas": {}, "candado": threading.Lock()}


def registro(mensaje: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {mensaje}", flush=True)


class Servidor(BaseHTTPRequestHandler):
    """R2 falso (/bucket/...) y endpoint de callback (/callback) de Django."""

    def _responder(self, codigo: int, cuerpo: bytes = b"") -> None:
        self.send_response(codigo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self) -> None:
        clave = urllib.request.unquote(self.path.split("?", 1)[0].removeprefix("/bucket/"))
        ruta = AUDIOS / clave.removeprefix("entradas/")
        if clave.startswith("entradas/") and ruta.is_file():
            self._responder(200, ruta.read_bytes())
        else:
            self._responder(404)  # como una URL prefirmada vencida

    def do_PUT(self) -> None:
        clave = self.path.split("?", 1)[0].removeprefix("/bucket/")
        datos = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        nombre = clave.rsplit("/", 1)[-1]
        if self.headers.get("Content-Type") != TIPOS.get(nombre):
            self._responder(403)  # R2 rechaza si el Content-Type no es el firmado
            return
        destino = RESULTADOS / clave
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
        with estado["candado"]:
            estado["subidas"][clave] = self.headers.get("Content-Type")
        self._responder(200)

    def do_POST(self) -> None:
        datos = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.headers.get("X-Worker-Token") != TOKEN:
            with estado["candado"]:
                estado["rechazados"] += 1
            self._responder(403)
            return
        with estado["candado"]:
            estado["callbacks"].append((time.time(), json.loads(datos)))
        self._responder(204)

    def log_message(self, *_args) -> None:
        pass


def http_json(metodo: str, url: str, cuerpo: dict | None = None) -> tuple[int, dict, dict]:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    pedido = urllib.request.Request(url, data=datos, method=metodo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


def esperar_worker() -> dict:
    for _ in range(180):
        try:
            codigo, cuerpo, _ = http_json("GET", f"{WORKER}/salud")
            if codigo == 200:
                return cuerpo
        except OSError:
            pass
        time.sleep(1)
    registro("El worker no respondió /salud en 3 minutos")
    sys.exit(1)


def despachar(nombre: str, url_entrada: str) -> dict:
    job_id = str(uuid.uuid4())
    solicitud = {
        "jobId": job_id, "version": 1, "parametros": {}, "inputUrls": [url_entrada],
        "outputUploadUrls": {n: f"{PROPIO}/bucket/jobs/{job_id}/{n}?{FIRMA}" for n in TIPOS},
        "callbackUrl": f"{PROPIO}/callback",
    }
    reintentos_503 = 0
    while True:
        codigo, _, encabezados = http_json("POST", f"{WORKER}/procesar", solicitud)
        if codigo == 202:
            registro(f"despachado {nombre} → {job_id[:8]} (tras {reintentos_503} respuesta(s) 503)")
            return {"nombre": nombre, "jobId": job_id, "despachado": time.time(), "reintentos503": reintentos_503}
        if codigo == 503:
            reintentos_503 += 1
            time.sleep(min(float(encabezados.get("Retry-After", 5)), 5))
            continue
        raise RuntimeError(f"POST /procesar devolvió {codigo} para {nombre}")


def esperar_final(job: dict, limite_segundos: float = 300) -> dict:
    while time.time() - job["despachado"] < limite_segundos:
        with estado["candado"]:
            finales = [(t, c) for t, c in estado["callbacks"]
                       if c["jobId"] == job["jobId"] and c["estado"] in ("COMPLETADO", "FALLIDO")]
        if finales:
            t, final = finales[-1]
            job["segundos"] = round(t - job["despachado"], 1)
            with estado["candado"]:
                primera = [tc for tc, c in estado["callbacks"]
                           if c["jobId"] == job["jobId"] and c.get("etapa") == "version-1-lista"]
            # Cuándo pudo escuchar el usuario la canción principal (antes que las alternativas).
            job["primeraCancion"] = round(primera[0] - job["despachado"], 1) if primera else None
            return final
        time.sleep(0.5)
    raise TimeoutError(f"El job {job['nombre']} no terminó en {limite_segundos} s")


def main() -> int:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    servidor = ThreadingHTTPServer(("0.0.0.0", 9000), Servidor)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    salud = esperar_worker()
    registro(f"worker listo: {salud}")

    validos = sorted(p.name for p in AUDIOS.glob("*.m4a")) + ["02 T.wav"]
    casos = [(n, f"{PROPIO}/bucket/entradas/{urllib.request.quote(n)}?{FIRMA}", "COMPLETADO", None) for n in validos]
    casos.append(("01 T.wav (muy corto)", f"{PROPIO}/bucket/entradas/01%20T.wav?{FIRMA}", "FALLIDO", "ENTRADA_INVALIDA"))
    casos.append(("URL vencida", f"{PROPIO}/bucket/entradas/ya-no-existe.m4a?{FIRMA}", "FALLIDO", "ERROR_INTERNO"))

    inicio = time.time()
    # Se despachan de a uno, a medida que el worker acepta: con capacidad 2,
    # el tercero recibe 503 y se reintenta, como haría el despachador de Django.
    trabajos = []
    hilos = []
    for nombre, url, esperado, codigo in casos:
        job = despachar(nombre, url)
        job.update(esperado=esperado, codigoEsperado=codigo)
        trabajos.append(job)
        hilo = threading.Thread(target=lambda j=job: j.update(final=esperar_final(j)))
        hilo.start()
        hilos.append(hilo)
    for hilo in hilos:
        hilo.join()
    total = round(time.time() - inicio, 1)

    fallas = []
    filas = []
    for job in trabajos:
        final = job["final"]
        etapas = [c["etapa"] for _, c in estado["callbacks"] if c["jobId"] == job["jobId"] and c["estado"] == "PROCESANDO"]
        ok = final["estado"] == job["esperado"] and final.get("codigoError") == job["codigoEsperado"]
        versiones = (final.get("metadatos") or {}).get("versiones", [])
        if final["estado"] == "COMPLETADO":
            subidas = [k for k in estado["subidas"] if k.startswith(f"jobs/{job['jobId']}/")]
            esperadas = 5 + 2 * (len(versiones) - 1)  # la principal + partitura + alternativas
            ok = (ok and len(subidas) == esperadas and job["primeraCancion"] is not None
                  and all("firma" not in u for u in final["outputUrls"]))
        if not ok:
            fallas.append(job["nombre"])
        m = final.get("metadatos") or {}
        filas.append({
            "tarareo": job["nombre"], "jobId": job["jobId"], "estado": final["estado"],
            "codigoError": final.get("codigoError"), "error": final.get("error"), "segundos": job["segundos"],
            "reintentos503": job["reintentos503"], "etapasReportadas": etapas,
            "estilo": m.get("estilo"), "estiloMensaje": m.get("estiloMensaje"), "variante": m.get("variante"),
            "bpm": m.get("bpm"), "tonalidad": m.get("tonalidad"), "acordes": m.get("acordes"),
            "duracionCancion": m.get("duracionCancionSegundos"), "lufs": m.get("loudnessLufs"), "ok": ok,
            "primeraCancion": job.get("primeraCancion"), "versiones": [v["estilo"] for v in versiones],
        })
        detalle = (f"{' + '.join(v['estilo'] for v in versiones)} | 1.ª canción a los {job.get('primeraCancion')} s"
                   if final["estado"] == "COMPLETADO" else f"{final.get('codigoError')}: {final.get('error')}")
        registro(f"{'OK  ' if ok else 'FALLA'} {job['nombre']:22} {final['estado']:10} {job['segundos']:5.1f}s  "
                 f"{len(etapas)} avisos de progreso  {detalle}")

    informe = {"total_segundos": total, "callbacks_rechazados_por_token": estado["rechazados"],
               "subidas": len(estado["subidas"]), "jobs": filas, "fallas": fallas}
    (RESULTADOS / "informe.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    registro(f"{len(trabajos) - len(fallas)}/{len(trabajos)} casos OK en {total} s; "
             f"{len(estado['subidas'])} archivos subidos; {estado['rechazados']} callbacks sin token válido")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
