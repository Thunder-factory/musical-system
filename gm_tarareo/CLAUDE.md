# Worker de Tarareo → Canción — contexto del proyecto

> Documento único del proyecto: lo leen automáticamente los agentes (Claude
> Code) al abrir esta carpeta. Reemplaza a los antiguos `PROMPT-tarareo.md` y
> `AGENTS.md`. El detalle vive en:
> - `docs/ARQUITECTURA.md`: arquitectura de la plataforma (debate y decisiones)
> - `docs/PLAN-TARAREO.md`: plan de las etapas que faltan
>
> Última actualización: 2026-11-14 (reingeniería: React + Django + R2 + PostgreSQL).

---

## ROL

Actuá como un ingeniero de software senior especializado en **procesamiento de
audio (MIR - Music Information Retrieval)** y **backends asíncronos en Python**.
Trabajamos de forma incremental: construimos por etapas y cada etapa se prueba
antes de pasar a la siguiente. No generes el proyecto entero de golpe.

---

## CONTEXTO DEL PROYECTO GENERAL

Somos un equipo de 5 estudiantes de Ingeniería de Software construyendo una
plataforma **web** (y móvil, pendiente de definir cómo) de procesamiento musical con IA. Cada integrante
desarrolla una funcionalidad independiente; al final todas se integran bajo
**un mismo login y una misma interfaz**.

Las 5 funcionalidades comparten la forma
`archivo multimedia → procesamiento pesado → archivo multimedia`:

| # | Funcionalidad | Entrada | Salida |
|---|---------------|---------|--------|
| 1 | Separación de sonidos | video/audio | pistas separadas |
| 2 | Generación de videoclip | MP3 | imágenes/video |
| 3 | Face Swap | foto + video | usuario en personajes |
| 4 | Traducción musical | video | video traducido |
| 5 | **Tarareo → Canción** | voz/tarareo | **canción generada** ← LA MÍA |

### Arquitectura (resumen de `docs/ARQUITECTURA.md`)

> **Reingeniería del 2026-11-14:** Angular → **React**, Spring Boot →
> **Django**, MinIO → **Cloudflare R2**. PostgreSQL se mantiene. El pipeline
> del worker no cambia; cambian quién lo llama y dónde viven los binarios.

```
React ──JWT──► Django (monolito modular: apps auth · jobs · storage)
                 │ tabla `jobs` en Postgres + despachador (select_for_update skip_locked)
                 │ POST /procesar ──► 5 workers Python (servicios aparte, caja negra)
                 │ ◄── callback de progreso/fin (con token compartido)
          PostgreSQL (metadatos, JSONB)   Cloudflare R2 (binarios, URLs prefirmadas)
```

- Django **no procesa IA**: solo orquesta. Toda la IA vive en los workers.
- ⚠️ **El worker NO se importa dentro de Django** aunque ambos sean Python:
  arrastraría Python 3.11 + TensorFlow 2.15 + NumPy < 2 al backend de todos y
  cargaría ~1.2 GB de modelo en cada proceso web. Sigue siendo un servicio HTTP.
- Los workers **nunca** tocan la base. Leen y escriben en R2 con URLs
  prefirmadas (GET/PUT) que Django genera **al despachar** el job. El worker
  **no tiene credenciales de R2** ni usa `boto3`.
- R2 es externo: el worker necesita salida a internet, limitada a
  `*.r2.cloudflarestorage.com` y al backend.
- El núcleo del worker no conoce el transporte: `ejecutar_job(sobre) -> resultado`.
  HTTP es un adaptador; si mañana se usa una cola, se cambia solo el adaptador.
- Workers GPU (face swap, generativo) con capacidad propia, separada de los CPU.
- Front: SSE (Django bajo ASGI) + polling de respaldo.
- ⚠️ **Pendiente de decisión del equipo** (detalle en `docs/ARQUITECTURA.md`):
  1. Cola: tabla `jobs` en Postgres (recomendada) o Celery + broker (Redis/RabbitMQ).
  2. ¿Hay app móvil? ¿React Native o web responsive? Define el formato de grabación.
  3. Claves del contrato en `camelCase` (recomendado, es lo que hay) o `snake_case`.

---

## MI FUNCIONALIDAD: TARAREO → CANCIÓN

### Objetivo

Que una persona **sin conocimientos musicales ni instrumentos** capture una
melodía que tiene en la cabeza tarareándola al micrófono, y reciba a cambio una
**canción producida**: con ritmo, armonía, instrumentación y estructura.
Resuelve el problema de la "idea musical que se pierde".

### Objetivos específicos

1. Capturar audio del micrófono en el navegador y en el móvil, de forma robusta
2. Extraer la melodía real (notas, duraciones) de un tarareo imperfecto y desafinado
3. Inferir el contexto musical: tempo (BPM), tonalidad y una progresión de acordes coherente
4. **Inferir el estilo del propio tarareo** y generar la canción en ese estilo
5. Entregar el resultado como MP3 descargable y como MIDI editable

> ⚠️ **Genera, no identifica.** El sistema **no** reconoce ni busca qué
> canción existente se tarareó (no es un "Shazam de tarareos"). Genera una
> canción original a partir de lo que entiende del tarareo: la melodía, su
> tempo, su tonalidad y su forma de cantarse. Ninguna etapa ni test depende de
> saber "qué canción era".
>
> ⚠️ **El usuario NO elige género de antemano.** Solo tararea. El sistema
> infiere el estilo y genera **hasta 3 versiones** en los estilos que encajan
> (la principal primero, las alternativas después); el usuario elige la que
> más le gusta **escuchando**, no de una lista de géneros (2026-11-14).
>
> Detalle original: El estilo y la
> instrumentación se derivan del análisis: tempo, modo mayor/menor, densidad
> rítmica, contorno y articulación. No diseñar etapas que dependan de un
> parámetro `genero`.

### Entrada / Salida

**Entrada:**
- Audio de **8 a 30 segundos de sonido útil** (óptimo 15-20 s), en cualquier
  formato del navegador: `webm/opus` (Chrome, Android) o `m4a/aac` (Safari/iOS).
  Si hay app React Native, el grabador tiene que fijarse en AAC 44.1 kHz mono:
  los presets AMR-NB a 8 kHz (`.3gp`) los convierte ffmpeg, pero basic-pitch
  pierde precisión.
  Debajo de 8 s la detección de tempo no es confiable; arriba de 30 s no aporta
  nada, porque el tarareo es una semilla, no la canción. Los 8 s se miden
  **después de recortar los silencios**.
- Parámetros opcionales: tempo deseado y duración objetivo. Si llega un
  `genero`, se acepta (`extra="allow"`) pero no se usa.

**Salida:**
- `cancion.mp3`: audio final
- `melodia.mid` (y `arreglo.mid`): MIDI editable
- `analisis.json`: melodía, BPM, tonalidad, acordes, estilo inferido, confianza y notas descartadas

---

## STACK OBLIGATORIO Y POR QUÉ

No sustituyas estas elecciones sin avisar y explicar el motivo.

### Worker

| Tecnología | Por qué esta |
|---|---|
| **Python 3.11** | ⚠️ **Obligatorio.** La traba real es **TensorFlow 2.15**, que basic-pitch 0.4.0 exige en Windows con Python ≥ 3.11 y que no tiene wheels para 3.12+. 3.10 ya no recibe soporte (oct-2026); 3.11 tiene soporte hasta oct-2027. |
| **FastAPI + Uvicorn** | Async nativo, validación con Pydantic y OpenAPI generado (sirve para acordar el contrato con el equipo). |
| **librosa** | Estándar en MIR: tempo, onsets, análisis espectral, recorte de silencios. |
| **basic-pitch 0.4.0** (Spotify) | CNN preentrenada audio→MIDI, corre en CPU, Apache 2.0, pensada para audio monofónico. Es la última versión publicada. |
| **pretty_midi** | Manipulación de MIDI con una API limpia. |
| **music21** (MIT) | Teoría musical: tonalidad, escalas, armonización. |
| **ffmpeg** | Normalización de formatos; cada plataforma graba distinto. |
| **FluidSynth + SoundFont** | Render determinista de MIDI a audio, sin GPU. La licencia del SoundFont tiene que permitir uso comercial. |
| **NumPy < 2.0** | ⚠️ TensorFlow 2.15 y basic-pitch rompen con NumPy 2.x. |

**Backend ONNX (aplicado en Docker el 2026-11-14):** el paquete basic-pitch
incluye el modelo en ONNX (`saved_models/icassp_2022/nmp.onnx`). La imagen
Docker instala basic-pitch con `--no-deps` + `onnxruntime` (ver
`requirements-docker.txt`), sin TensorFlow. Verificado con los 9 tarareos
del lote: **mismas notas, nota por nota** que TensorFlow. El entorno de
desarrollo en Windows sigue con TensorFlow (`requirements.txt` sin cambios).

### Infraestructura

| Tecnología | Por qué |
|---|---|
| **PostgreSQL** | `parametros` como `JSONB`: cada worker guarda su forma sin migrar el esquema compartido. |
| **Cloudflare R2** | Compatible con S3 y sin costo de egress (descargar MP3 sale gratis). Los binarios **nunca** van en la base. El PUT prefirmado tiene que mandar el mismo `Content-Type` con que se firmó. R2 no soporta subida por formulario (POST): el front sube con PUT o multipart prefirmado, y el bucket necesita CORS. En desarrollo local se puede usar MinIO como sustituto S3: al worker le da igual, solo ve URLs. |
| **Docker** | Los 5 integrantes levantan el mismo entorno con un comando (perfiles `cpu` y `gpu`). |

### Backend (lo construye el equipo, no este repo)

| Tecnología | Qué implica para el worker |
|---|---|
| **Django** | Llama a `POST /procesar` y recibe el callback. La cola puede ser la tabla `jobs` con `select_for_update(skip_locked=True)` (soportado por el ORM en Postgres) o Celery; en ambos casos la tarea de Django **solo despacha**, no corre IA. |

### Frontend (integración posterior)

| Tecnología | Por qué |
|---|---|
| **React** | Elegido por el equipo en la reingeniería. Si hay móvil (React Native o web responsive) está pendiente de decisión. |
| **MediaRecorder API** | Captura en el navegador (webm/opus en Chrome, mp4/aac en Safari). |

### Etapa generativa (opcional, al final)

| Tecnología | Estado |
|---|---|
| **ACE-Step** | Candidato. Modo audio2audio usando el render de FluidSynth como referencia. **Verificar la licencia de los pesos y la VRAM real antes de comprometerse.** Corre solo en un worker GPU; si no hay GPU, se entrega el render de FluidSynth. |
| ~~MusicGen~~ | Descartado: pesos CC BY-NC (no comercial). |
| ~~Suno API~~ | Descartado: no existe una API pública oficial. |
| ~~YuE2 (ianiv/YuE2)~~ | Descartado: solo Apple Silicon (MLX), Python 3.12, pesos CC BY-NC, ~13 GB. Sirve como referencia de ideas. |
| ~~YuE2-Studio (timoncool)~~ | Descartado: Rust/Tauri + yue2.cpp, requiere NVIDIA ≥ 6 GB, pesos CC BY-NC. Sirve como referencia de ideas. |

---

## RESTRICCIONES NO NEGOCIABLES

1. **No entrenamos ningún modelo.** Todo es inferencia con modelos preentrenados.
2. **Todo es asíncrono.** El endpoint responde `202 Accepted` con el `jobId` al
   instante y nunca bloquea esperando el procesamiento.
3. **El worker es una caja negra.** No conoce Django ni React, ni toca la base de
   datos del backend, ni tiene credenciales de R2. Recibe URLs y devuelve archivos.
4. **Debe funcionar sin GPU.** Las etapas 1 a 8 corren en CPU. La GPU es opcional
   y solo para la etapa generativa.
5. **Etapas separadas y testeables.** Cada etapa es un módulo que se ejecuta y se
   prueba de forma aislada.
6. **Manejo explícito de tarareos malos.** Si la señal no sirve, el sistema
   devuelve un error claro y accionable. Nunca devuelve silencio ni ruido.
7. **Licencias compatibles con uso comercial** en modelos, pesos y SoundFonts.

---

## CONTRATO CON EL EQUIPO

Implementado (versión 1, 2026-11-14). JSON Schema en `contratos/v1/`
(generado desde `app/modelos.py` con `python -m app.contrato`; un test falla
si se desincroniza). Guía para el lado Django: `docs/INTEGRACION-DJANGO.md`.

```
POST /procesar
  body: { jobId (UUID), version: 1, parametros: {...}, inputUrls: [...],
          outputUploadUrls?: {"cancion.mp3": URL PUT, "melodia.mid": ..., "arreglo.mid": ..., "analisis.json": ...},
          callbackUrl? }
  202 { jobId, estado: "PROCESANDO" }  |  503 + Retry-After si está lleno  |  422 si está mal armada

GET /salud
  200 { estado: "ok", version, modelosCargados, capacidad, ocupados }

GET /jobs/{id}
  200 ResultadoJob | 404

POST {callbackUrl}   header X-Worker-Token: <TARAREO_CALLBACK_TOKEN>
  uno por etapa (PROCESANDO, progreso, etapa) y uno final (reintentado 3 veces)
  body: { jobId, estado, progreso, etapa, outputUrls: [...], error, codigoError, metadatos: {...} }
```

- Estados: `PENDIENTE | PROCESANDO | COMPLETADO | FALLIDO`.
- `codigoError`: `ENTRADA_INVALIDA` (definitivo: el audio no sirve, no
  reintentar) | `ERROR_INTERNO` (transitorio: red, URL vencida, servidor).
- Con `outputUploadUrls`, el worker sube cada salida a R2 con su Content-Type
  fijo (`TIPOS_SALIDA`), devuelve las URLs **sin firma** y borra su copia
  local. Sin `outputUploadUrls` (desarrollo), `outputUrls` son rutas locales.
- `parametros.genero` ya no existe (se acepta como extra y se ignora).

---

## PIPELINE TÉCNICO

```
1. INGESTA        cualquier formato → WAV mono 22050 Hz (ffmpeg)              ✅
2. PREPROCESADO   recortar silencios, validar señal y duración útil,
                  normalizar volumen → si no sirve, fallar temprano            ✅
3. MELODÍA        basic-pitch → notas MIDI + confianza                         ✅
4. LIMPIEZA       las 4 reglas medidas (ver abajo)                             ✅
5. ANÁLISIS       pulso (medido o puesto por el sistema) + tonalidad           ✅
6. ARMONÍA        progresión de acordes coherente con la melodía y la tonalidad ✅
6.5 ESTILO        inferido del tarareo con reglas explicables (no lo elige el usuario) ✅
7. ARREGLO        plan de estructura → instrumentos y patrones según el estilo ✅
8. RENDER         MIDI → audio (FluidSynth) → loudness → MP3                  ✅
9. GENERATIVA     opcional, GPU (ACE-Step), detrás de la interfaz Generador
```

El detalle de las etapas 5 a 9 y las ideas tomadas de las repos de referencia
están en `docs/PLAN-TARAREO.md`.

### Etapa 4: reglas de limpieza (MEDIDAS, no inventadas)

Con un tarareo real de 16.8 s (`tests/audio/mi_tarareo.wav`), basic-pitch
devolvió **30 notas** donde había ~15. Las reglas se aplican **en este orden**
(cada una asume el resultado de la anterior; el motivo está en el docstring
de `limpieza.py`):

| # | Defecto observado | Ejemplo real | Regla |
|---|---|---|---|
| 1 | **Nota partida en dos** | `A#2 1.90→2.11` + `A#2 2.11→3.00` | Fusionar notas del mismo pitch con hueco `< 50 ms` (o solapadas). La nota fusionada nunca se acorta. Va primero porque un fundamental fragmentado puede no solaparse con su armónico. |
| 2 | **Duplicación de octava** | `A#3(58) 1.88→2.61` junto a `A#2(46) 1.90→2.11` | Si dos notas se solapan y difieren **exactamente 12 semitonos**, conservar la **más cercana a la mediana** de pitches. Se desempata por amplitud solo si quedan a la misma distancia (la amplitud a veces favorecía al armónico). |
| 3 | **Espuria fuera de rango** | `D6(86) 5.61→5.78 amp=0.34` | Descartar lo que caiga fuera de ±1 octava de la mediana (recalculada). |
| 4 | **Fragmentos débiles** | varias con `amp < 0.4` | Descartar `amplitud < 0.40` o `duración < 80 ms`. |

Cada nota descartada queda en `analisis.json` con su motivo.

### Representación intermedia (después de la etapa 6)

Es la pieza clave: desacopla el análisis de la generación. Cualquier generador
(FluidSynth, ACE-Step, otro) consume este mismo JSON.

```json
{
  "melodia": [{"nota": 62, "inicio": 0.0, "duracion": 0.5, "velocidad": 90}],
  "bpm": 96,
  "tonalidad": "G major",
  "compas": "4/4",
  "acordes": ["G", "D", "Em", "C"],
  "estilo": {"preset": "pop", "motivo": "BPM 96 + densidad media"},
  "confianza": 0.83
}
```

---

## ESTRUCTURA DEL PROYECTO

```
worker-tarareo/
├─ app/
│  ├─ main.py              adaptador HTTP (FastAPI): /procesar, /salud, /jobs/{id}
│  ├─ nucleo.py            ejecutar_job(solicitud) -> ResultadoJob, sin transporte
│  ├─ capacidad.py         cupos de jobs simultáneos (503 si está lleno)
│  ├─ calentamiento.py     compila numba de antemano (build y arranque)
│  ├─ almacenamiento.py    subida de salidas a R2 (PUT prefirmado)
│  ├─ reintentos.py        reintentos con espera creciente (red, 5xx)
│  ├─ retencion.py         límites de jobs en memoria y de salidas/
│  ├─ contrato.py          genera contratos/v1/*.schema.json
│  ├─ demo.py + demo.html  demo en vivo /demo (SOLO modo desarrollo): grabar y escuchar
│  ├─ config.py            configuración por variables de entorno (TARAREO_*)
│  ├─ modelos.py           esquemas Pydantic del contrato y del dominio
│  └─ pipeline/
│     ├─ excepciones.py    ErrorPipeline / ErrorIngesta / ErrorAudioInvalido
│     ├─ ingesta.py        ffmpeg → WAV normalizado
│     ├─ preprocesado.py   recortar, validar señal y duración, normalizar
│     ├─ melodia.py        basic-pitch → notas crudas
│     ├─ limpieza.py       las 4 reglas de la etapa 4
│     ├─ analisis.py       etapa 5: pulso (medido o libre), tonalidad, cuantización
│     ├─ armonia.py        etapa 6: acordes por programación dinámica
│     ├─ estilo.py         etapa 6.5: estilo inferido (tabla de 6 perfiles)
│     ├─ arreglo.py        etapa 7: estructura + instrumentación (tabla de estilos)
│     ├─ render.py         etapa 8: FluidSynth → acabado → ebur128/ganancia → MP3
│     ├─ masterizacion.py  EQ y compresión suaves, ambiente moderado
│     └─ salida.py         escribir melodia.mid y analisis.json
├─ tests/                  pytest; audios reales en tests/audio/ (wav + m4a)
├─ contratos/v1/          JSON Schema del contrato con Django (generado)
├─ docs/                   ARQUITECTURA.md, PLAN-TARAREO.md, LICENCIAS.md, INTEGRACION-DJANGO.md
├─ herramientas/           FluidSynth + SoundFont locales (ignorado por git)
├─ probar.py               pipeline sobre un archivo local sin servidor (--lote)
├─ Dockerfile              targets worker (producción) y pruebas; backend ONNX
├─ docker-compose.yml      levanta solo este worker
├─ docker-compose.integracion.yml  worker + simulador de Django/R2 (prueba de punta a punta)
├─ integracion/            simulador_django.py
├─ requirements-docker.txt dependencias de la imagen (onnxruntime, sin TensorFlow)
├─ probar_entorno.py       smoke test del stack completo
├─ requirements.txt        ← versiones probadas juntas; no tocar sin acordar
├─ .env.example
└─ README.md
```

---

## ESTADO ACTUAL Y PRÓXIMOS PASOS

### Etapa 1: esqueleto + ingesta → limpieza ✅ (2026-11-03)

- [x] `POST /procesar` responde 202 al instante (`BackgroundTasks`)
- [x] Acepta `webm`, `m4a`, `wav` y `mp3`
- [x] Silencio, ruido o poco sonido útil → `FALLIDO` con mensaje claro
- [x] No quedan pares solapados a 12 semitonos exactos
- [x] `pytest` pasa (41 tests). ⚠️ El test de latencia es inestable con la
      máquina cargada (ver deuda técnica)
- [x] Lote de grabaciones validado (2026-11-14, `python probar.py --lote tests/audio`):
      11/13 con melodía; los 2 rechazos son `01 T` (4.8 s, demasiado corta,
      correcto). En las de ~17 s, 5/6 quedan en 12-18 notas (`04 T` da 21).
      mp3/wav/m4a de la misma grabación dan resultados idénticos.
      **Bug corregido:** `08 T` (tarareo bajito con pausas) se rechazaba como
      silencio; ahora SIN_SENAL usa el p95 del RMS en ventanas de 50 ms en vez
      del RMS global (ver `calcular_dbfs_activo`)

Bugs corregidos el 2026-11-03: la fusión acortaba notas contenidas en otra; la
duración mínima se validaba antes de recortar los silencios.

### Bloque 1: preparar el worker para Django ✅ (2026-11-14)

- [x] Núcleo agnóstico al transporte: `app/nucleo.py` (`ejecutar_job`), nunca
      lanza; `main.py` quedó como adaptador HTTP
- [x] Modelo de basic-pitch cargado **una vez** al arrancar (`lifespan`) y
      reutilizado; `/salud` ya no importa TensorFlow (responde en ~4 ms)
- [x] `TARAREO_CAPACIDAD` (default 2): `/salud` expone `capacidad`/`ocupados`;
      si está lleno, `/procesar` → **503 + `Retry-After`**. El cupo se libera
      aunque el job explote
- [x] `jobId` validado como **UUID** (422 si no); la carpeta sale de `str(UUID)`
- [x] Rutas locales/`file://` solo con `TARAREO_MODO_DESARROLLO=true`
      (default `false`); límite de tamaño de descarga (25 MB)
- [x] Las URLs prefirmadas no se filtran: errores y logs sin query string,
      logger de `httpx` en WARNING
- [x] Reenvío de un job que sigue en proceso → 202 sin duplicarlo
- [x] Progreso real por etapa visible en `GET /jobs/{id}` (5→20→40→80→90→100)
- [x] `pytest`: 68 tests pasan; suite en ~67 s (antes 98 s, el modelo ya no se recarga)

### Etapa 5: ANÁLISIS ✅ (2026-11-14)

- [x] `app/pipeline/analisis.py`: tempo por alineación de onsets a una grilla
      de corcheas × preferencia de tempo × densidad (nota típica entre corchea y
      negra) + librosa como segunda opinión; tonalidad Krumhansl-Schmuckler
      (music21) ponderada por duración; cuantización suave a semicorcheas
- [x] Sintéticos (±20 ms): 100 % exacto o al doble/mitad, 93 % exacto; tests
      estrictos ±5 % en 66-128 BPM. A 145 puede leerse a la mitad (documentado)
- [x] **Hallazgo con el lote real:** los tarareos reales son de ritmo libre
      (rubato, pausas de 2-5 s): su alineación a cualquier grilla no supera la
      de notas al azar, y librosa tampoco coincide (37-215 BPM)
- [x] **Opción A (decidida 2026-11-14): si no hay pulso, el sistema lo pone.**
      El pulso se juzga contra el azar (misma cantidad de notas, mismo lapso,
      60 simulaciones, percentil 95). `ritmo: "medido"` → tempo detectado +
      cuantización suave. `ritmo: "libre"` → tempo por la nota típica (sin
      contar pausas) y ritmo reescrito por proporciones a valores musicales
      (¼ a 4 tiempos); pausas entre frases → silencio de 1-2 tiempos. Se
      conservan alturas, orden y largo/corto. `confianzaBpm` ahora es relativa
      al azar; `motivoRitmo` explica la decisión
- [x] `melodia.mid` se escribe desde la melodía en pulsos (cae en la grilla)
- [x] Lote real: las 10 grabaciones válidas salen `libre`, tempos 62-126
- [x] `probar.py --escucha`: `escucha_melodia.wav` (melodía en tiempo +
      metrónomo); si el ritmo es medido, también el tarareo con click
- [x] OK de oído del usuario con `escucha_melodia.wav` (2026-11-14): las
      melodías regularizadas se reconocen y el ritmo suena natural
- [x] `pytest`: 147 tests

### Etapa 6: ARMONÍA ✅ (2026-11-14)

- [x] `app/pipeline/armonia.py`: tríadas diatónicas (en menor también V
      mayor), ajuste ponderado por duración y tiempo fuerte, programación
      dinámica con transiciones funcionales (V→I, ii→V, IV→V...), bonus por
      empezar/terminar en tónica, penalización por repetir; un acorde por
      compás o dos si ninguno cubre ≥ 60 %; anacrusa detectada (0-3 pulsos)
- [x] Salida en `analisis.json` → `armonia`: `acordes` (lista simple del JSON
      intermedio), `progresion` (compás, inicio, duración, grado, notas,
      cobertura) y `anacrusaPulsos`
- [x] 16 tests sintéticos; suite completa 163 tests
- [x] Lote real: progresiones plausibles (p. ej. `05 T`: Bm Em F# Bm…).
      Cobertura 0.00 = compás sin melodía (la pausa entre frases): el acorde
      sale solo de las transiciones. `09 T` y `mi_tarareo` cierran en IV/VII
      porque la última frase encaja mejor ahí que en la tónica
- [x] OK de oído del usuario con `escucha_armonia.wav` (2026-11-14): los
      acordes acompañan la melodía

### Etapa 6.5: ESTILO INFERIDO ✅ (2026-11-14)

- [x] `app/pipeline/estilo.py`: 6 rasgos (tempo, modo, densidad,
      articulación con el timing original sin contar pausas, rango, saltos)
      comparados con una TABLA de perfiles (`PERFILES`); gana el de mayor
      puntaje; empate práctico (< 0.03) → el más neutro
      (pop > folk > balada > lofi > rock_suave > epico)
- [x] 6 estilos: balada, pop, rock_suave, lofi, folk, epico. Descartados por
      no medibles: bossa, reggae, vals (síncopa / compás de 3). Pendiente para
      después: electrónico/dance (requiere medir repetición de motivos) → hecho, ver abajo
- [x] `motivo` nombra solo rasgos que encajan con el estilo (puntaje ≥ 0.75)
- [x] Lote real: lofi ×4, rock_suave ×2, balada, folk, pop (epico no aparece:
      los tarareos del lote tienen rango corto, 3-9 semitonos)
- [x] **Bug corregido de paso:** ruido blanco podía dar 2 notas con confianza
      0.437 (> 0.42) y pasar la etapa de melodía; ahora también se exigen
      ≥ 4 notas crudas. El fixture de ruido tenía semilla aleatoria (test
      inestable): fijada en la semilla 4, el caso difícil
- [x] `pytest`: 176 tests
- [x] OK del usuario (2026-11-14): el estilo coincide con la sensación de
      cada tarareo del lote
- La variedad dentro de cada estilo (2-3 variantes de arreglo) va en la etapa 7
- [x] **Mejoras (2026-11-14, pedidas por el usuario):**
      - Rasgo `repeticion`: fracción de figuras de 4 notas (3 intervalos) que
        se repiten, aunque estén transpuestas o con otro ritmo. Lote real:
        0.00-0.22; azar 0.00; motivo repetido 1.00
      - **7.º estilo: electrónico** (repetición ≥ 0.5 + 110-135 BPM), con su
        arreglo (bombo en negras, palmas, hi-hat abierto a contratiempo, bajo
        de sintetizador, 3 variantes de lead). Pop ahora prefiere repetición
        ≤ 0.5 (si no, empataba con electrónico)
      - Confianza del estilo: `confianza` (margen sobre el 2.º / 0.25),
        `alternativa`, `ambiguo` (margen < 0.08) y `mensaje` para el usuario
        ("Tu tarareo suena entre balada y lo-fi; la canción va en balada.").
        También en `metadatos` del job (`estiloMensaje`, `estiloAmbiguo`)
      - Calibración: `probar.py --lote` exporta `estilos.csv`;
        `tests/audio/estilos_validados.csv` guarda los 9 tarareos validados
        de oído y un test verifica que ningún cambio les cambie el estilo.
        Lote: 3 de 9 son ambiguos (03 T, 04 T, 05 T), los 9 conservan su estilo
- [x] `pytest`: 244 tests

### Etapa 7: ARREGLO ✅ (2026-11-14)

- [x] `app/pipeline/arreglo.py`: estructura planificada primero
      (intro → A → A' → B → A final → outro), ajustada a 60-90 s quitando o
      agregando A'/B. A = el tarareo; B = progresión IV-V-vi-V (VI-VII-iv-V en
      menor) con el primer motivo del tarareo transpuesto diatónicamente
- [x] TABLA `ESTILOS`: por estilo, patrón de acompañamiento, bajo y batería +
      3 variantes de instrumentación GM (18 en total). Variante por rasgos
      (p. ej. balada muy ligada → cuerdas) o, si no deciden, por huella de la
      melodía: mismo tarareo → misma canción
- [x] Séptimas en balada y lofi solo si la melodía no canta a un semitono;
      anacrusa respetada (la nota de entrada suena al final de la sección
      anterior); la melodía nunca se pisa a sí misma; velocity humanizada
      determinista
- [x] Salida: `arreglo.mid` (multipista, batería en canal 10) y `arreglo` en
      `analisis.json`; `outputUrls` ahora tiene 3 archivos
- [x] 35 tests (los 18 estilo×variante incluidos); suite completa 211 tests
- [x] Lote real: 9 canciones de 61-86 s, variantes distintas
- [x] `probar.py --escucha` → `escucha_arreglo.wav`: maqueta sin FluidSynth
      (tonos simples + batería sintética); juzga estructura, no timbre
- [x] Primera escucha del usuario: "parece que sí"; pidió mejoras
- [x] **Mejoras (2026-11-14, las 4 pedidas):**
      - Transiciones y bajo: enlace de voces (inversión que menos se mueve),
        redoble en los tiempos 3-4 del último compás de cada sección con
        batería + platillo al entrar, bajo con aproximación cromática antes
        de cada cambio de acorde (pop, rock, lofi)
      - Variedad: B elige 1 de 3 progresiones por huella (todas terminan en
        V); patrón de acompañamiento liviano en intro/A/B y lleno en A'/A final
      - Melodía que evoluciona: pista "Segunda voz" con el gancho (primer
        motivo) en la intro, doblaje a la octava en A' y terceras diatónicas
        por debajo en A final
      - Dinámica y final: crescendo de 2 compases antes de A' y A final
        (+25 %), ritardando en el outro (posiciones estiradas, MIDI a tempo
        constante) y fermata de 2 pulsos en el acorde final
- [x] 44 tests del arreglo; suite completa 220 tests; lote real 62-89 s
- [x] OK de oído del usuario con las mejoras (2026-11-14)

### Etapa 8: RENDER ✅ (2026-11-14)

- [x] **Acabado ligero (2026-11-14):** `masterizacion.py`, paso alto 30 Hz,
      EQ ancha (-1.2 dB a 280 Hz, +0.6 dB a 2800 Hz), compresión RMS 1.3:1
      con canales enlazados. Se modera la reverb ya presente en FluidSynth
      (nivel 0.18, sala 0.30, amortiguación 0.55), sin añadir otro eco.
      `TARAREO_RENDER_MASTERIZACION=true` por defecto, desactivable para
      comparar al mismo volumen (-16 LUFS). Se aplica a todas las versiones;
      `render.masterizacion` registra el perfil. Ver `docs/MASTERIZACION.md`.
- [x] Validación del acabado: 49 tests relacionados en Windows y 16 en
      Docker; 9 canciones del lote con MP3 finales entre -16.2 y -16.3 LUFS,
      picos bajo -1 dBTP. Comparaciones antes/después en
      `salidas/masterizacion/` (lo-fi y rock suave); falta preferencia de oído.
- [x] FluidSynth 2.6.2 (release oficial, hash verificado) y FluidR3_GM.sf2
      (**MIT**, paquete Debian estable, hash verificado) en `herramientas/`
      (ignorado por git). Registro de licencias en `docs/LICENCIAS.md`
- [x] `app/pipeline/render.py`: FluidSynth por línea de comandos (sin
      dependencias nuevas) → recorte + fade de la cola de reverb (2.5 s) →
      medición `ebur128` + ganancia + limitador a -16 LUFS / -1 dBTP → MP3 192 kbps con
      metadatos. ~1-2 s de render por canción
- [x] Balance de pistas en `arreglo.mid` (CC7 volumen + CC10 panorama por rol)
- [x] Sin FluidSynth/SoundFont → `ErrorRender` con mensaje que aclara que es
      del servidor, no del tarareo. Rutas: `TARAREO_FLUIDSYNTH`,
      `TARAREO_SOUNDFONT`; si no se configuran, se buscan en `herramientas/`
- [x] `outputUrls`: `cancion.mp3`, `melodia.mid`, `arreglo.mid`, `analisis.json`;
      `analisis.json` → `render` (duración, LUFS, pico, SoundFont y licencia)
- [x] 7 tests de render (los que necesitan FluidSynth se saltean si falta);
      suite completa 227 tests
- [x] Lote real: 9 canciones de 65-92 s
- [x] Primera escucha del usuario (2026-11-14): bien, con 2 correcciones
      aplicadas: (1) melodía más clara → mezcla con la melodía ~4 dB más
      adelante que el resto; (2) volumen general más bajo → -16 LUFS (antes
      -14). Lote regenerado: todas -16.0 ±0.2 LUFS
- [x] SoundFont alternativo: **MuseScore General** 0.2.1 (MIT, partes PD/CC0,
      con origen de cada muestra; paquete Debian, hash verificado) instalado
      en `herramientas/soundfonts/`. El usuario comparó y le parecen bien los
      dos. **Por defecto queda FluidR3** (render ~1.3 s contra ~16 s del .sf3
      comprimido; en Docker es `fluid-soundfont-gm`). MuseScore General se
      usa con `TARAREO_SOUNDFONT=.../MuseScore_General_Full.sf3`
      **GeneralUser GS descartado:** su licencia permite uso comercial pero
      el autor no garantiza el origen de todas las muestras (Debian lo
      considera no libre)

### Docker + backend ONNX ✅ (2026-11-14)

- [x] `Dockerfile` (base `python:3.11-slim-trixie`, targets `worker` y
      `pruebas`), `requirements-docker.txt`, `.dockerignore`,
      `docker-compose.yml` (solo este worker). ffmpeg, FluidSynth y
      FluidR3_GM desde apt. Usuario sin privilegios (uid 10001),
      `TARAREO_MODO_DESARROLLO=false`, healthcheck contra `/salud`
- [x] **Backend ONNX solo en Docker:** basic-pitch con `--no-deps` +
      onnxruntime 1.31.1, sin TensorFlow. `requirements.txt` (Windows, TF)
      no cambió y el código tampoco (basic-pitch elige ONNX si no hay TF).
      **Verificado: mismas notas que TensorFlow en los 9 tarareos del lote**
      (0 ms de diferencia en tiempos, 0.000 en amplitud)
- [x] Imagen: ~620 MB comprimida, ~1.65 GB instalada. RAM en reposo 252 MB.
      Arranque 19 s (incluye calentamiento)
- [x] **numba:** el primer job de cada contenedor tardaba 104 s (librosa
      compilando). `app/calentamiento.py` compila al construir la imagen
      (`NUMBA_CACHE_DIR` en la imagen) y otra vez al arrancar. Primer job en
      frío: 23 s; siguientes ~19 s (antes de optimizar el render; después,
      15 s y 12 s, ver punto 4b del orden siguiente)
- [x] Job completo en el contenedor en modo producción (entrada por URL
      http desde otro contenedor que simula R2): COMPLETADO, mismo resultado
      que en Windows; la firma de la URL no aparece en los logs
- [x] Suite completa dentro de Linux: 244 tests pasan

### Bloque 2: integración con Django y R2 ✅ (2026-11-14)

- [x] Contrato v1 (ver "CONTRATO CON EL EQUIPO"): `version`,
      `outputUploadUrls`, `etapa`, `codigoError`, callbacks de progreso,
      token `X-Worker-Token`. JSON Schema en `contratos/v1/` + test de sincronía
- [x] `app/almacenamiento.py`: PUT prefirmado a R2 con Content-Type fijo,
      reintentos (500 sí, 403 no), URLs devueltas sin firma; la carpeta local
      se borra al subir
- [x] Errores clasificados: `ErrorPipeline.codigo` (audio inválido / archivo
      corrupto → ENTRADA_INVALIDA; descarga, ffmpeg ausente, render, subida →
      ERROR_INTERNO)
- [x] `app/reintentos.py`: espera 1-2-4 s, solo red/timeout/5xx
- [x] `docs/INTEGRACION-DJANGO.md`: cómo firmar URLs de R2 con boto3, payload,
      vista del callback con `hmac.compare_digest`, cuándo reintentar,
      despachador con `select_for_update(skip_locked=True)`
- [x] Tests contra un R2 falso (`servidor_r2` en conftest): subida, 500
      transitorio, 403 vencida sin firma en el mensaje, job completo subiendo
      los 4 archivos, callbacks de progreso + final con token, reintento del
      callback, el token no aparece en logs. Suite: 267 tests
- [x] **Prueba de integración en Docker** (2026-11-14):
      `docker compose -f docker-compose.integracion.yml up --build --abort-on-container-exit --exit-code-from simulador`.
      `integracion/simulador_django.py` hace de Django + R2: despacha todos los
      tarareos con URLs de subida, reintenta ante 503, verifica el token de los
      callbacks y el Content-Type de cada subida. Resultado: **11/11 casos OK**
      (9 canciones, tarareo corto → ENTRADA_INVALIDA, URL vencida →
      ERROR_INTERNO), 36 archivos subidos, ~18 s por canción con 2 a la vez
- [ ] Probar contra un bucket R2 real de desarrollo (cuando el equipo lo cree)

### Versiones alternativas ✅ (2026-11-14, pedido del usuario)

- [x] Etapa 6.5 devuelve `alternativas`: otros estilos con puntaje ≥ 0.6
      (máx. 2). Ej.: mi_tarareo → lo-fi + balada + épico; 06 T → rock + pop
- [x] El núcleo termina y ENTREGA la principal primero (`version-1-lista`, con
      `outputUrls` parciales en el aviso de progreso) y después genera cada
      alternativa (`alternativa-N` → `version-N-lista`). Si una alternativa
      falla, el job igual termina COMPLETADO con la principal
- [x] Salidas nuevas: `cancion-2.mp3`, `arreglo-2.mid`, `cancion-3.mp3`,
      `arreglo-3.mid` (nombres por posición: Django firma antes de saber los
      estilos); `analisis.json` → `versiones`; `metadatos.versiones`
- [x] `TARAREO_VERSIONES_MAXIMAS` (1-3, por defecto 3)
- [x] Demo: muestra la principal apenas está, agrega las alternativas sin
      cortar la reproducción, y "Me gusta esta" guarda la elección en
      `salidas/elecciones.csv` con los rasgos (mismo formato que
      `estilos_validados.csv`: sirve para calibrar)

### Demo en vivo ✅ (2026-11-14)

- [x] `http://localhost:8000/demo` con `TARAREO_MODO_DESARROLLO=true`: grabar
      con el micrófono (o subir un audio), ver el avance por etapa y escuchar
      y descargar la canción. La subida crea un job por el mismo camino que
      POST /procesar. En producción las rutas /demo no existen (test lo verifica)
- Levantar: `$env:TARAREO_MODO_DESARROLLO="true"; venv\Scripts\python -m uvicorn app.main:app --port 8000`

### Deuda técnica conocida (antes de integrar con Django)

1. ~~Modelo recargado en cada job / `/salud` bloqueante~~ ✅ bloque 1
2. ~~Sin límite de jobs simultáneos~~ ✅ bloque 1
3. ~~`jobId` sin validar, rutas locales en producción~~ ✅ bloque 1
4. ~~`salidas/` y `trabajos` crecen sin límite; callback sin reintento~~ ✅
   2026-11-14: `app/retencion.py` (`RegistroJobs` con retención de 60 min y
   máximo 1000; `purgar_salidas` borra carpetas de más de 24 h, nunca las de
   jobs en proceso) + reintento del callback final
5. ~~`outputUrls` con rutas locales~~ ✅ bloque 2 (subida a R2)
8. ~~Callback sin autenticar~~ ✅ bloque 2 (`X-Worker-Token`)
9. Pendiente menor: `tempoDeseado` y `duracionObjetivo` se aceptan pero no
   se usan (el tempo sale del tarareo; la duración la fija el arreglo)
6. ~~`requirements.txt` con paquetes sin usar y versiones abiertas~~ ✅
   2026-11-14: sin `pydub` ni `python-multipart`; todo fijado
7. ~~Campo `genero` en `modelos.py`~~ ✅ 2026-11-14: quitado del contrato

### Orden siguiente (detalle en `docs/PLAN-TARAREO.md`)

1. ~~Validar la limpieza con el lote de grabaciones~~ ✅ 2026-11-14.
2. ~~Deuda técnica 1-3 + núcleo agnóstico al transporte~~ ✅ bloque 1.
2b. ~~Bloque 2, integración con Django/R2~~ ✅ 2026-11-14.
3. ~~Etapas 5 → 6 → 6.5 → 7 → 8~~ ✅ 2026-11-14.
4. ~~Dockerfile + backend ONNX~~ ✅ 2026-11-14.
4b. ~~Optimizar el render~~ ✅ 2026-11-14: `ebur128` mide, después ganancia
    exacta + limitador de seguridad (`alimiter`, 0.5 dB de margen) y MP3 en
    la misma pasada. En Docker: primer job 23 s → 15 s; siguientes 19 s →
    12 s. Lote: -16.0 LUFS (±0.1), picos ≤ -1.3 dBTP. 245 tests.
5. Etapa 9 generativa (opcional).

---

### Muestras rápidas, partitura y expresión (2026-11-14)

- [x] Demo: muestras de 16 s por estilo; botón "Escuchar completa" separado
      de "Elegir como favorita". Cada completa usa el análisis guardado sin
      repetir IA. Clics repetidos siguen el mismo job y la caché en archivos
      sobrevive a reinicios, durante la retención de 24 h.
- [x] Anticipación solo mientras se escucha una completa y hay capacidad
      libre; se reserva un cupo para peticiones explícitas. No se generan
      todas las completas por adelantado.
- [x] Contrato aditivo: `operacion=generar|muestras|completar` y
      `versionElegida`; por defecto sigue `generar`. Para completar en
      producción, `inputUrls[0]` es el GET firmado del análisis original.
      Django conserva las completas en R2. Ver `docs/MUESTRAS-Y-VERSIONES.md`.
- [x] `partitura.musicxml`: melodía, silencios, tempo, tonalidad y cifrado
      de acordes, reabierta en pruebas con music21. Solo se redondea la
      notación, sin alterar el MIDI.
- [x] `expresion.py`: reutiliza pitch bends de basic-pitch, suavizados y
      centrados (no copiar desafinado constante), límite ±0.35 semitonos.
      Solo en la melodía de instrumentos sostenidos, sin cambiar las notas.
      Desactivable con `TARAREO_MELODIA_EXPRESIVA=false`.
- [x] Pruebas: lectura de partitura, expresión y límites de bends, ausencia
      de bend en piano/percusión, muestras recortadas, clics duplicados,
      caché tras reiniciar registro y completar desde R2 sin repetir IA.
- [x] Validación: 296 tests en Docker con ONNX; suite de 292 en Windows más
      los 4 casos añadidos de caché/R2, todos pasan. Imagen worker:dev
      reconstruida. Demo local en puerto 8002: tres muestras en 13.17 s,
      completar en 9.43–10.74 s y recuperar la caché en 12–19 ms. Son medidas
      de esta máquina, no garantías de latencia en otros servidores.

### Estribillo y variedad rítmica ✅ (2026-11-14)

Actualización musical (puntos 4 y 5): `pipeline/gancho.py` busca
frases repetidas por intervalos y ritmo. Sin evidencia propone una frase y
lo declara con confianza 0. A conserva el verso original; A' y A final
repiten el gancho con sus acordes como estribillos. `estructura[].funcion`
explica el rol sin romper los identificadores internos. `patrones.py`
ofrece base/aire/impulso por estilo, sin mutar las tablas. Ambos ajustes
están activos en el pipeline y se pueden desactivar por configuración.
Las muestras usan el estribillo cuando existe y la caché pasa a v3.
Detalle: `docs/ESTRIBILLO-Y-PATRONES.md`.

Validación: suite completa 312 tests en Windows; 79 tests relacionados en
Docker/ONNX. Flujo en vivo verificado en puerto 8003: muestras, completas
bajo demanda y reutilización de caché. Imagen worker:dev reconstruida.

### Instrumentación reforzada y clima musical ✅ (2026-11-15)

- `pipeline/clima.py`: sugerencia serena, melancólica, luminosa, enérgica o
  intensa por rasgos musicales. No atribuye emociones a la persona; declara
  ambigüedad y confianza de reglas (sin calibración perceptual).
- `pipeline/instrumentacion.py`: dos capas por estilo con notas de los acordes,
  entradas por sección y reemplazos si el timbre ya está en la base. Sustituye
  el colchón anterior; máximo dos apoyos simultáneos contando la segunda voz.
- El clima ajusta suavemente la intensidad del apoyo y algunos timbres; la
  melodía y el tempo permanecen. Mezcla de colores detrás de la melodía,
  volumen final -16 LUFS. Sin GPU, descargas ni dependencias nuevas.
- `arreglo.clima` en el análisis, `metadatos.clima` en el resultado y explicación
  en la demo. Ajustes activos: `arreglo_clima_musical` e
  `arreglo_instrumentacion_ampliada`. Caché de completas v4.
- Detalle y límites: `docs/CLIMA-E-INSTRUMENTOS.md`.
- Validación: 376 tests pasan en Windows y 87 relacionados en Docker/ONNX;
  revisión de código y sintaxis de la demo correctas. Imagen worker:dev
  reconstruida. Demo de Docker en puerto 8004 mediante
  `docker-compose.demo.yml`, con volumen propio para evitar la lentitud de
  escritura de WAV en carpetas compartidas de Windows. No se hizo commit.
- Flujo HTTP real: tres muestras 9.75 s; completas 8.10/8.62 s; caché 9/17 ms.
  Muestras y completas con MIDI idéntico y mismo clima. Siete muestras de
  comparación en `salidas/estilos-reforzados/`; estilos forzados solo para
  diagnóstico, no como recomendaciones del clasificador.

### Interpretación acústica y ritmo fiel (2026-11-15)

- `pipeline/interpretacion.py`: segunda opinión YIN con energía, periodicidad,
  estabilidad y presencia espectral de la fundamental. Referencia de afinación
  por grabación; correcciones conservadoras de hasta un semitono, sin imponer
  escala ni transponer octavas por YIN. Ajustes en `analisis.json` → `interpretacion`.
- Limpieza conserva notas amplias o tenues corroboradas por la señal. El modelo
  puede aceptar confianza baja solo con respaldo acústico suficiente; silencio
  y señales sin altura estable siguen siendo errores claros.
- Ritmo libre por posiciones absolutas, ajuste máximo 0.10 pulsos, tresillos y
  silencios reales; no se comprimen notas sostenidas. Expresión nueva al 40 %
  (máximo 14 cents). Ajustes configurables; caché v5; YIN se precalienta.
- Pruebas con melodías sintéticas nuevas, registros MIDI 36–98, ±38 cents,
  cromatismos, saltos amplios, ruido y desplazamiento temporal acumulado.
- Se compararon las tres grabaciones recientes de la demo: una dio melodía y
  dos siguieron sin altura suficientemente corroborada. A/B en
  `salidas/revision-interpretacion/`; no afirmar que se interpreta cualquier
  ruido ni que existe una mejora auditiva universal.
- Ver `docs/INTERPRETACION-TARAREO.md`. Evaluación de ACE-Step 1.5, Qwen2,
  SDXL-Turbo y Demucs en `docs/PLAN-TARAREO.md`: candidatos, no instalados.
- Validación final: 400 tests pasan en Docker/ONNX, 24 nuevos casos de
  interpretación pasan en Windows (más 192 relacionados en la primera ronda).
  Revisión de código y sintaxis de la demo correctas. Imagen reconstruida.
- Demo 8004 actualizada y verificada por HTTP: muestras 9.71 s, completas
  8.12/7.08 s, caché 10 ms; MIDI idéntico entre muestra y completa.
- Confirmación auditiva del usuario (2026-11-15): la interpretación mejoró;
  se mantiene esta revisión como base para las siguientes etapas.

### Gráfico y parecido melódico (2026-11-19)

- `pipeline/grafico.py`: `analisis.json` y los metadatos finales traen `grafico`
  (`GraficoTarareo`): curva YIN de la voz cada 50 ms (`None` = sin voz), notas
  detectadas y melodía cuantizada, todo en segundos del tarareo. `medir_alturas`
  se calcula una vez y lo reusa `verificar_alturas`; si falla, el job sigue sin curva.
- `POST /parecido` + `pipeline/parecido.py`: cuánto de la pista "Melodía" de
  `arreglo-N.mid` suena en un audio con IA. basic-pitch transcribe el audio y se
  cuenta el acierto por clase de altura (±100 ms), descontando el azar. Calibrado:
  FluidSynth 0.97; covers del mismo tarareo 0.40-0.47 (0.21-0.33 con fidelidad
  libre); otras melodías ≤ 0.10. El croma del audio completo NO sirve (medía
  tonalidad/armonía: covers de otro tarareo puntuaban igual). De a una medición a la vez.

### Versiones en paralelo (2026-11-19)

- `nucleo.py`: las alternativas se generan en hilos a la vez que la principal
  (`TARAREO_VERSIONES_PARALELAS`, por defecto 3; 1 = como antes). La principal
  se entrega primero y las alternativas en orden de número, así el progreso
  nunca retrocede; solo el hilo principal escribe `analisis.json`. El render ya
  usaba nombres de archivo por versión, así que no hay pisadas.
- Medido en Docker: versiones listas a los 24 / 29 / 34 s (antes 20 / 33 / 47 s).
  Cada job usa hasta 3 núcleos: tener en cuenta `TARAREO_CAPACIDAD`.
- Test nuevo: en paralelo y en serie dan las mismas versiones y los mismos avisos.
  Suite completa en Docker: 401 tests pasan.

## QUÉ **NO** HACER

- No generar varias etapas del pipeline de una sola vez
- No usar TensorFlow directamente; basic-pitch maneja su propio backend
- No meter lógica de negocio en `main.py`; va en `pipeline/`
- No usar `print()`; usar `logging` con niveles
- No guardar archivos en rutas absolutas ni hardcodeadas
- No asumir que el audio de entrada es válido; validar siempre
- No agregar dependencias sin justificarlas
- No diseñar nada que dependa de que el usuario elija un género
- No adoptar modelos o pesos con licencia no comercial (CC BY-NC)
- No importar el pipeline dentro de Django ni agregar `boto3`/credenciales de R2 al worker

---

## MI ENTORNO

- **Windows 11**, terminal PowerShell
- **Python 3.11** (convive con un 3.14 del sistema → invocar siempre con
  `py -3.11` o con `venv\Scripts\python`)
- Node 24.19, Git 2.55 (Java 21 y Angular CLI quedaron del stack anterior)
- ffmpeg instalado y en el PATH (9.0.1, con `loudnorm` y `libmp3lame`)
- FluidSynth 2.6.2 + FluidR3_GM.sf2 en `herramientas/` (ver `docs/LICENCIAS.md`)
- **Sin GPU NVIDIA**: todo debe correr en CPU
- Editor: VS Code

---

## CÓMO TRABAJAMOS

- Explicar **por qué** se elige cada cosa, no solo el código
- Código y comentarios en **español**
- Nombres de variables y funciones en español, salvo términos técnicos
  establecidos (pitch, onset, MIDI, BPM)
- Antes de escribir el código de una etapa, explicar el plan y esperar el OK
- Si una decisión tiene alternativas reales, mostrarlas con sus trade-offs
- Si algo de este documento es técnicamente incorrecto o hay una forma mejor,
  decirlo en vez de seguirlo a ciegas
- Al cerrar una etapa, actualizar la sección "Estado actual" de este archivo
