# Arquitectura de la plataforma — propuesta para el equipo

> Resultado de un debate entre cuatro sesiones de agentes (2026-11-02), con
> ángulos distintos: propuesta inicial, robustez, simplicidad y operación. Es una
> **propuesta**: los cambios al contrato acordado (marcados con 🔶) hay que
> acordarlos con los otros 4 integrantes antes de implementarlos.
>
> **Actualizado el 2026-11-14 por la reingeniería del stack:** Angular +
> Capacitor → **React**, Spring Boot → **Django**, MinIO → **Cloudflare R2**.
> PostgreSQL se mantiene. Las decisiones del debate siguen valiendo; cambió la
> tecnología con que se implementan. Lo que cambió está en la sección
> "Reingeniería" al final.

## Decisión en una línea

**Monolito modular en Django + tabla de jobs en PostgreSQL + workers Python
por HTTP (servicios aparte) + Cloudflare R2 con URLs prefirmadas.** No se usa
un broker de mensajes por ahora, pero queda la puerta abierta.

```
React (web; móvil pendiente de decisión)
   │  HTTPS + JWT        (subida directa a R2 con URL prefirmada de PUT)
   ▼
Django  ─ apps: auth · jobs · storage · una por funcionalidad
   │  despachador: toma jobs PENDIENTES de la tabla y despacha
   │  POST /procesar ───────────────►  worker-separacion   (CPU)
   │                                   worker-videoclip    (GPU)
   │                                   worker-faceswap     (GPU)
   │                                   worker-traduccion   (CPU/GPU)
   │  ◄──── callback (progreso/fin)    worker-tarareo      (CPU)
   ▼                                        │  GET/PUT prefirmados
PostgreSQL (jobs, usuarios, parametros JSONB)    ▼
                                         Cloudflare R2 (binarios)
```

## Las decisiones y por qué

| # | Decisión | Por qué | Alternativa descartada |
|---|---|---|---|
| 1 | **Django como monolito modular** (un solo deploy, con apps `auth`, `jobs`, `storage` y una por funcionalidad) | 5 estudiantes no pueden operar N servicios. Las apps de Django dan la misma separación lógica sin costo de despliegue. | Microservicios en el backend |
| 2 | **Tabla `jobs` en Postgres como cola** (`estado`, `intentos`, `timeout_en`, `worker`), y un despachador (comando de management en un loop) que toma pendientes con `Job.objects.select_for_update(skip_locked=True)` dentro de una transacción | Da no perder jobs, reintentos y control de carga sin agregar una pieza nueva. El ORM de Django lo soporta nativo en Postgres. | Celery + Redis/RabbitMQ (ver "Desacuerdo"). |
| 3 | **Interfaz `DespachadorJobs` en Django** (una clase Python con una implementación HTTP) | Si algún día hace falta Celery o RabbitMQ, se cambia la implementación y los workers no se enteran. | — |
| 4 | **Los workers se quedan en HTTP** (`POST /procesar` → 202 + callback), que es lo ya acordado, y son **servicios aparte de Django** | Respeta el contrato existente y "el worker es una caja negra": nunca toca la base. Que Django también sea Python **no** es razón para importar los workers adentro (ver decisión 22). | Workers leyendo la tabla directamente. Workers importados como librerías dentro de Django. |
| 5 | **El núcleo del worker no conoce el transporte**: `ejecutar_job(sobre) -> resultado`. HTTP es solo un adaptador. | Permite cambiar a una cola sin tocar el pipeline, y testear sin servidor. | — |
| 6 | 🔶 **Control de carga en el worker**: `/salud` expone `capacidad` y `ocupados`. Si está lleno, `/procesar` responde **503** y Django reintenta más tarde. | Es el equivalente a `prefetch=1`: evita que 10 jobs simultáneos llenen la RAM. | Aceptar todo y encolar en memoria del worker. |
| 7 | **Timeout por funcionalidad**: si un job queda en `PROCESANDO` más allá de `timeout_en`, Django lo reintenta hasta N veces y después lo marca `FALLIDO`. | Cubre reinicios del worker, porque `BackgroundTasks` se pierde. | — |
| 8 | 🔶 **Errores clasificados**: `codigoError` = `ENTRADA_INVALIDA` (definitivo, no se reintenta) o `ERROR_INTERNO` (transitorio, se reintenta) | Reintentar un tarareo en silencio es desperdicio. Un fallo de red merece otro intento. | Reintentar todo. |
| 9 | **Binarios solo en R2**: el front sube directo con una URL prefirmada de PUT. 🔶 El worker recibe `inputUrls` (GET) y `outputUploadUrls` (PUT) **generadas por Django al despachar**, no al crear el job. | No pasan binarios por Django. Generar las URLs al despachar evita que venzan mientras el job espera en la tabla. El worker no necesita credenciales de R2. | Subir los archivos a través de Django. URLs generadas al crear el job (vencen). Dar credenciales de R2 a cada worker. |
| 10 | 🔶 **Callbacks de progreso** (`progreso` 0-100 + `etapa`), no solo el final | Los jobs duran minutos; el usuario tiene que ver que avanza. | — |
| 11 | **Notificación al front: SSE + polling de respaldo** (`GET /jobs/{id}` cada 2-3 s) | SSE en Django necesita ASGI (con WSGI cada conexión abierta ocupa un proceso). El polling cubre al móvil en segundo plano y a los proxies que cortan conexiones largas. | Solo WebSocket (Django Channels) o solo SSE. |
| 12 | **Capacidad separada para GPU**: los workers GPU (face swap, generativo) tienen su propia capacidad y timeouts largos | Un job GPU de 10 min no debe bloquear a los de CPU. | — |
| 13 | **Contrato versionado** en una carpeta `/contratos` (JSON Schema del sobre del job). Cada worker valida su propio `parametros`. | Un repo aparte sobra para 5 personas. | Repo de contratos separado. |
| 14 | **Seguridad**: workers solo accesibles desde la red interna (Django es el único que los llama), límites de tamaño y duración validados en Django **antes** de encolar, `jobId` como UUID validado, 🔶 **callback autenticado con un token compartido** en un header | Los workers no tienen auth propia. Como ahora salen a internet (R2), el aislamiento de red ya no alcanza para proteger el callback. | — |
| 15 | **Operación**: un `docker-compose.yml` con todo, `jobId` como correlation-id en todos los logs, **reglas de ciclo de vida de R2** como TTL de limpieza de binarios, cancelación de jobs | Cada integrante levanta todo con un comando y prueba su worker aislado con `POST /procesar` + fixtures. | — |

## Aportes de operación (incorporados)

| # | Decisión | Por qué |
|---|---|---|
| 16 | **Latido (heartbeat) de progreso** cada N segundos. Django detecta un job colgado por falta de latido, no solo por duración total. | Los jobs GPU varían mucho: un timeout fijo mata jobs sanos o tarda en detectar los muertos. Complementa la decisión 7. |
| 17 | **Subida multipart prefirmada a R2** para archivos grandes; Django crea el job recién cuando confirma que el objeto existe (`HEAD`) y valida tamaño, tipo y duración | Con conexiones inestables se reanuda solo la parte que falló. R2 no soporta subida por formulario (POST), solo PUT y multipart. |
| 18 | **Perfiles de docker-compose** `cpu` y `gpu` | Cada integrante levanta solo lo suyo |
| 19 | **SDK mínimo de worker** compartido (recibir job, latido, subir resultado) + modo CLI `python -m worker --job job.json` | Los 5 workers no reimplementan lo mismo; se prueban sin levantar nada |
| 20 | **Worker falso** que responde al instante + **tests de contrato** contra el JSON Schema en CI | El front y Django se desarrollan sin GPU ni modelos |
| 21 | Workers en una red interna **sin puertos expuestos**; **salida a internet limitada** a R2 (`*.r2.cloudflarestorage.com`), al backend y a las APIs externas que use cada worker; URLs prefirmadas de vida corta; validar el tipo real del archivo (no la extensión) | Reduce la superficie de ataque. Antes era "sin salida a internet"; con R2 eso ya no es posible. |
| 22 | **Los workers no se importan dentro de Django** | Cada worker tiene dependencias propias y pesadas (tarareo: Python 3.11 + TensorFlow 2.15 + NumPy < 2). Meterlas en Django las impone a todo el backend y carga los modelos en cada proceso web. |

## Desacuerdo registrado: ¿cola en la tabla o un broker?

Antes el debate era "RabbitMQ sí o no". Con Django aparece la variante
natural del ecosistema, **Celery**, pero la pregunta de fondo es la misma:
¿se agrega un broker (Redis o RabbitMQ)?

- **A favor de un broker ahora** (3 de las 4 posturas iniciales): una
  cola por tipo de recurso, `prefetch=1`, ack solo al terminar, límite de
  reintentos y DLQ. Con Django, Celery es lo estándar y hay mucha documentación.
- **En contra por ahora** (postura de simplicidad): todo eso se logra con la
  tabla `jobs` + `skip_locked` + 503 cuando el worker está lleno, sin una pieza
  más que operar. Además respeta el contrato HTTP ya acordado.

**Recomendación de esta síntesis:** empezar con la tabla de jobs (decisión 2).
Si el equipo elige Celery, dos condiciones:

1. La tarea de Celery es **solo el despachador** (hace el `POST /procesar`).
   La IA sigue en los workers, no en los procesos de Celery de Django.
2. Si más adelante los workers consumen directo de la cola, el cambio queda
   en el adaptador del worker gracias a la decisión 5.

## Cambios al contrato (🔶) — implementados en el worker de tarareo (2026-11-14)

> Contrato v1 en `contratos/v1/` del repo del worker; guía para Django en
> `docs/INTEGRACION-DJANGO.md`. Los otros 4 workers pueden copiar el mismo contrato.

```
POST /procesar
  body: { jobId, version, parametros, inputUrls, outputUploadUrls, callbackUrl }
  202 { jobId, estado: "PROCESANDO" }  |  503 si el worker está lleno

GET /salud
  200 { estado, version, modelosCargados, capacidad, ocupados }

POST {callbackUrl}
  header: X-Worker-Token: <secreto compartido>
  { jobId, estado, progreso, etapa, outputUrls, error, codigoError, metadatos }
```

Detalles nuevos por usar R2:

- `outputUploadUrls` es un mapa `nombre de archivo → URL PUT prefirmada`
  (por ejemplo `{"melodia.mid": "...", "analisis.json": "..."}`), así el
  worker sabe qué sube a dónde. Cada worker documenta sus nombres de salida.
- El `Content-Type` de cada salida queda fijado en el contrato
  (`audio/mpeg`, `audio/midi`, `application/json`): si el PUT manda uno
  distinto del que se usó al firmar, R2 rechaza la subida.
- **Claves en `camelCase`** (como hoy), aunque Django/DRF use `snake_case`
  por dentro: se decide una vez para los 5 workers y Django mapea.

## Cuándo reconsiderar un broker

Cuando aparezca al menos una de estas: más de una réplica por worker, picos de
cientos de jobs en espera, o necesidad de que los workers corran fuera de la red
de Django. Gracias a las decisiones 3 y 5, el cambio queda acotado a un
adaptador de cada lado.

## Reingeniería del 2026-11-14: qué cambió

| Antes | Ahora | Impacto en los workers |
|---|---|---|
| Spring Boot | Django | Ninguno en el pipeline: el contrato es HTTP + JSON. Riesgo: la tentación de importar los workers en Django (decisión 22). |
| MinIO | Cloudflare R2 | Compatible con S3; las URLs prefirmadas funcionan igual. Los workers ahora necesitan salida a internet (decisión 21) y deben subir sus salidas con PUT (decisión 9). |
| Angular + Capacitor | React | Ninguno directo. Si hay React Native, hay que fijar el formato de grabación. |
| PostgreSQL | PostgreSQL | Ninguno (los workers no tocan la base). |

**Pendiente de decisión del equipo:** cola (tabla o Celery), si hay app móvil
(React Native o web responsive), y `camelCase` o `snake_case` en el contrato.
