# Integración del worker de Tarareo con Django y R2

> Flujo interactivo recomendado: muestras cortas y versiones completas bajo
> demanda, con reutilización del análisis. Ver
> [MUESTRAS-Y-VERSIONES.md](MUESTRAS-Y-VERSIONES.md) para las operaciones,
> nombres de salida, caché y partitura MusicXML. `operacion: "generar"` mantiene
> el flujo de canciones completas descrito más abajo.

Guía para quien implemente el lado de Django. El contrato formal (JSON Schema)
está en [`contratos/v1/`](../contratos/v1/) y se genera desde el código del
worker, así que siempre está al día. Implementado el 2026-11-14 (bloque 2).

## El recorrido de un job

```
React ──sube el audio──► R2 (PUT prefirmado que le da Django)
Django: crea el job en la tabla `jobs` (PENDIENTE)
Django (despachador): toma el job, firma URLs, POST /procesar ──► worker
worker: 202 al instante ──► procesa ──► callbacks de progreso ──► sube a R2 ──► callback final
Django: guarda el resultado, avisa al front (SSE / polling)
```

## 1. Firmar las URLs al despachar (no al crear el job)

El worker **no tiene credenciales de R2**. Django firma, en el momento de
despachar, una URL GET para la entrada y una URL PUT por cada salida. Así no
vencen mientras el job espera en la tabla (decisión 9).

```python
import boto3
from botocore.config import Config

r2 = boto3.client(
    "s3",
    endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    region_name="auto",
    config=Config(signature_version="s3v4"),
)

# El Content-Type de cada salida es FIJO: el worker hace el PUT con este
# mismo valor, y si no coincide con el que se firmó, R2 responde 403.
TIPOS_SALIDA = {
    "cancion.mp3": "audio/mpeg",
    "melodia.mid": "audio/midi",
    "arreglo.mid": "audio/midi",
    "analisis.json": "application/json",
    # Versiones alternativas en otros estilos (pueden no generarse: ver abajo).
    "cancion-2.mp3": "audio/mpeg",
    "arreglo-2.mid": "audio/midi",
    "cancion-3.mp3": "audio/mpeg",
    "arreglo-3.mid": "audio/midi",
    "muestra.mp3": "audio/mpeg",
    "muestra-2.mp3": "audio/mpeg",
    "muestra-3.mp3": "audio/mpeg",
    "partitura.musicxml": "application/vnd.recordare.musicxml+xml",
}

def urls_para(job):
    entrada = r2.generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET, "Key": job.clave_audio}, ExpiresIn=3600,
    )
    salidas = {
        nombre: r2.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET, "Key": f"jobs/{job.id}/{nombre}", "ContentType": tipo},
            ExpiresIn=3600,
        )
        for nombre, tipo in TIPOS_SALIDA.items()
    }
    return entrada, salidas
```

Django puede pedir solo algunas salidas (por ejemplo, solo `cancion.mp3` y
`analisis.json`): el worker sube únicamente las que vienen en el mapa.

## 2. Despachar: `POST /procesar`

```json
{
  "jobId": "1b272473-236f-4c92-a4d4-ff8c2b41657f",
  "version": 1,
  "parametros": {},
  "inputUrls": ["https://<cuenta>.r2.cloudflarestorage.com/tarareos/...?X-Amz-Signature=..."],
  "outputUploadUrls": {
    "cancion.mp3": "https://...cancion.mp3?X-Amz-Signature=...",
    "melodia.mid": "https://...",
    "arreglo.mid": "https://...",
    "analisis.json": "https://..."
  },
  "callbackUrl": "http://backend:8000/api/workers/tarareo/callback"
}
```

| Respuesta | Qué hacer |
|---|---|
| **202** `{jobId, estado: "PROCESANDO"}` | Marcar el job PROCESANDO y esperar callbacks |
| **503** + `Retry-After` | El worker está lleno: dejar el job PENDIENTE y reintentar después de esos segundos |
| **422** | La solicitud está mal armada (jobId no UUID, salida desconocida, versión distinta): es un bug de Django, no reintentar |

- `jobId` tiene que ser un UUID (`UUIDField` de Django ya lo es).
- Reenviar el mismo `jobId` mientras está en proceso no duplica el trabajo (202 sin hacer nada).
- `GET /salud` devuelve `capacidad` y `ocupados` para decidir antes de despachar.
- `parametros.genero` no existe: el estilo lo infiere el worker del tarareo.

## 3. Recibir el callback

El worker manda un `POST` a `callbackUrl` **en cada etapa** (progreso) y uno
**final**. Todos llevan el header `X-Worker-Token` con el secreto compartido
(`TARAREO_CALLBACK_TOKEN` en el worker): Django tiene que rechazar el callback
si no coincide.

```python
import hmac, json
from django.http import HttpResponse, HttpResponseForbidden

def callback_tarareo(request):
    token = request.headers.get("X-Worker-Token", "")
    if not hmac.compare_digest(token, settings.TARAREO_CALLBACK_TOKEN):
        return HttpResponseForbidden()
    datos = json.loads(request.body)
    job = Job.objects.get(id=datos["jobId"])
    # ...actualizar estado, progreso, etapa; si COMPLETADO, guardar outputUrls y metadatos
    return HttpResponse(status=204)
```

Cuerpo (`contratos/v1/resultado_job.schema.json`):

```json
{
  "jobId": "1b272473-...",
  "estado": "COMPLETADO",
  "progreso": 100,
  "etapa": "completado",
  "outputUrls": ["https://<cuenta>.r2.cloudflarestorage.com/<bucket>/jobs/1b27.../cancion.mp3", "..."],
  "error": null,
  "codigoError": null,
  "metadatos": {
    "bpm": 64.0, "tonalidad": "Bb minor", "acordes": ["Bbm", "Gb", "Ab", "Bbm", "Ebm", "Ab"],
    "estilo": "lofi", "estiloMensaje": "Tu tarareo suena a lo-fi.", "estiloAmbiguo": false,
    "duracionCancionSegundos": 91.6, "loudnessLufs": -16.0
  }
}
```

- Los callbacks de progreso traen `estado: "PROCESANDO"`, `progreso` (0-100) y
  `etapa` (`ingesta`, `melodia`, `armonia`, `render`, `subida`...). Sirven
  también de latido: si dejan de llegar, el job se colgó (decisión 16).
- `outputUrls` vienen **sin firma**: identifican el objeto. Para que el front
  descargue, Django firma una URL GET nueva.
- Responder 2xx. Si Django responde 5xx o no responde, el worker reintenta el
  callback final 3 veces (1 s, 2 s, 4 s). Uno de progreso perdido no se
  reintenta: el siguiente lo reemplaza.
- `estiloMensaje` está listo para mostrarle al usuario.

## 3b. Versiones: el usuario elige escuchando

El worker genera hasta **3 versiones** de la canción en los estilos que mejor
encajan con el tarareo, y entrega **primero la principal**:

1. Aviso de progreso con `etapa: "version-1-lista"` y `outputUrls` con la
   canción principal → el front ya puede reproducirla.
2. Avisos `alternativa-2` / `version-2-lista` (y la 3), con `outputUrls`
   acumulados, a medida que se generan.
3. Callback final COMPLETADO con todas las salidas y
   `metadatos.versiones` = `[{numero, estilo, variante, cancion, puntaje}]`.

Puede haber 1, 2 o 3 versiones: solo se proponen estilos que encajan (si el
tarareo es claramente rock, no se fuerza una balada). Las URLs firmadas de
versiones que no se generaron simplemente no se usan. Para no generar
alternativas: `TARAREO_VERSIONES_MAXIMAS=1` en el worker.

**La elección del usuario** (qué versión le gustó) conviene guardarla en
Django junto con `analisis.json → estilo.rasgos`: es la mejor fuente para
calibrar los estilos (`tests/audio/estilos_validados.csv` del worker).

## 4. Si el job falla: ¿reintentar?

| `codigoError` | Ejemplos | Qué hacer |
|---|---|---|
| `ENTRADA_INVALIDA` | silencio, ruido, menos de 8 s útiles, archivo corrupto | **No reintentar.** Mostrar `error` al usuario: está escrito para él ("Probá tararear más fuerte...") |
| `ERROR_INTERNO` | URL vencida, R2 caído, falla del servidor | **Reintentar** con URLs firmadas de nuevo, hasta N intentos |

`metadatos.motivo` (`SIN_SENAL`, `GRABACION_MUY_CORTA`, `SIN_MELODIA_CLARA`)
detalla por qué el audio no sirvió.

## 5. Despachador con la tabla `jobs` (decisión 2)

```python
from django.db import transaction

def despachar_pendientes():
    with transaction.atomic():
        jobs = list(
            Job.objects.select_for_update(skip_locked=True)
            .filter(estado="PENDIENTE", tipo="tarareo")[:capacidad_libre]
        )
        for job in jobs:
            job.estado = "DESPACHANDO"
            job.save(update_fields=["estado"])
    for job in jobs:
        entrada, salidas = urls_para(job)
        respuesta = httpx.post(f"{WORKER_URL}/procesar", json={...}, timeout=10)
        if respuesta.status_code == 503:
            job.estado = "PENDIENTE"  # reintentar más tarde
        ...
```

## Configuración del worker

| Variable | Valor en producción |
|---|---|
| `TARAREO_CALLBACK_TOKEN` | El mismo secreto que `settings.TARAREO_CALLBACK_TOKEN` de Django |
| `TARAREO_MODO_DESARROLLO` | `false` (ya es el valor de la imagen Docker) |
| `TARAREO_CAPACIDAD` | Jobs simultáneos (2 por defecto; medir en el servidor) |

El worker necesita salida a internet solo hacia R2
(`*.r2.cloudflarestorage.com`) y hacia Django (decisión 21).
