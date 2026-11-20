# Tarareo → Canción (fase 1)

El usuario tararea de 8 a 30 segundos y recibe hasta 3 canciones instrumentales construidas sobre **su** melodía. La versión que elige queda en su biblioteca como una canción más (`source_type='hummed'`).

## Piezas

| Pieza | Dónde | Qué hace |
|---|---|---|
| Worker de tarareo | `gm_tarareo/` (servicio `tarareo` en Docker) | Pipeline de audio: melodía con basic-pitch (ONNX), limpieza, pulso, tonalidad, acordes, estilo, arreglo, render con FluidSynth. Solo CPU. |
| App Django | `gm_backend/apps/humming/` | Recibe el tarareo, reserva créditos, firma URLs de R2, despacha al worker, recibe callbacks y crea la `Song`. |
| R2 | `humming/{user}/{job}/` | `entrada.<ext>` y `salidas/` (MP3, MIDI, partitura MusicXML, análisis). |

`gm_tarareo/` se trajo con `git subtree --squash` desde el repo del worker. Su documentación propia sigue en `gm_tarareo/CLAUDE.md` y `gm_tarareo/docs/`. Para traer cambios nuevos del worker:

```bash
git subtree pull --prefix=gm_tarareo --squash <ruta-o-url-del-worker> main
```

## Flujo

```
React ── POST /api/humming/ (archivo) ──► Django
Django: valida, reserva créditos, sube a R2, encola dispatch_humming_job
Celery: firma GET de la entrada y PUT de cada salida ──► POST http://tarareo:8000/procesar
Worker: 202 ──► procesa ──► sube a R2 ──► POST /api/humming/callback/ (X-Worker-Token)
Django: guarda metadatos y versiones, confirma el cobro
React ── GET /api/humming/{id}/ (polling) ──► versiones con URLs firmadas
React ── POST /api/humming/{id}/choose/ {version} ──► Song en la biblioteca
```

- **Callback** = camino principal. **Polling** (`poll_humming_job`, cada `HUMMING_POLL_INTERVAL_SECONDS`) = respaldo si se pierde un callback o el worker se reinicia.
- **Worker lleno (503)**: se reintenta tras `Retry-After`, sin gastar intentos.
- **`ENTRADA_INVALIDA`** (silencio, ruido, muy corto): falla definitiva, se liberan los créditos y `error_message` ya está escrito para el usuario.
- **`ERROR_INTERNO`** o worker que perdió el job: se vuelve a despachar con URLs nuevas, hasta `HUMMING_MAX_DISPATCH_ATTEMPTS`.
- El cobro se confirma solo cuando el worker termina bien.

## API

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/humming/` | multipart: `file` (webm, ogg, m4a, mp4, mp3, wav, aac, flac; ≤ 25 MB), `title` opcional. `202` con el job, `402` sin créditos, `400` formato inválido. |
| `GET` | `/api/humming/` | Tarareos del usuario. |
| `GET` | `/api/humming/{id}/` | `status`, `progress`, `stage`, `metadata` (bpm, tonalidad, acordes, estilo, estiloMensaje), `versions[]` (con `audio_url` y `midi_url`), `downloads` (melodía MIDI, partitura MusicXML). |
| `POST` | `/api/humming/{id}/choose/` | `{version: 1-3, title?}` → `201` con la canción. Repetir la misma versión devuelve la misma canción; elegir otra da `409`. |
| `POST` | `/api/humming/callback/` | Interno, solo para el worker. Requiere `X-Worker-Token`. |

## Configuración

En el `.env` de la raíz (ver `.env.example`, sección *TARAREO*):

```bash
# Obligatorio: sin token, Django rechaza todos los callbacks.
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copiar el valor a `TARAREO_CALLBACK_TOKEN`. Docker Compose se lo pasa al worker y Django lo lee del mismo `.env`. El resto de variables tiene valores por defecto que funcionan con `docker compose`.

## Probar

```bash
docker compose up -d --build tarareo backend celery-worker
docker compose exec backend python manage.py test apps.humming
```

Los tests del worker no vienen en su imagen (`target: worker` no copia `tests/` ni instala pytest). Se corren en un contenedor descartable con la misma imagen. Necesitan `TARAREO_MODO_DESARROLLO=true` porque usan rutas locales en lugar de URLs de R2; con el `false` de la imagen fallan 9 tests:

```bash
docker run --rm --memory=2g --user root -e TARAREO_MODO_DESARROLLO=true \
  -v "$PWD/gm_tarareo:/src:ro" -w /work --entrypoint sh musical-system-dev-tarareo -c \
  'cp -r /src/. /work/ && pip install -q --target /tmp/pt pytest && PYTHONPATH=/tmp/pt:/work python -m pytest -q -m "not slow"'
```

## Página "Tararear" (frontend)

`/humming` (`gm_frontend/src/pages/humming/`): grabación con `MediaRecorder` (webm/ogg/mp4 según el navegador) o subida de archivo, progreso por etapa, versiones en el reproductor global, elegir versión (crea la `Song`) y descargas de MIDI y partitura.

**Versiones progresivas:** en cada aviso `version-N-lista` del worker, Django lee el `analisis.json` recién subido a R2 y publica metadatos provisionales (`metadata.provisional = true`). La página muestra la versión principal apenas está (~20 s) con el mensaje "Escucha esta versión mientras creamos las demás…", y las alternativas aparecen solas a medida que llegan. Se puede elegir cuando terminan todas.

## Inspírate (melodías de ejemplo)

Para quien no sabe qué tararear: en la tarjeta de grabación, **"¿No sabes qué tararear? Inspírate"** genera una melodía corta (4 compases, ~9-14 s) en uno de 8 estilos (pop, balada, cumbia, rock, lo-fi, huayno, caporales, épico) o al azar. Se escucha con metrónomo, se ven las notas como barras y se puede pedir otra o grabarse imitándola.

Todo ocurre en el navegador (`gm_frontend/src/lib/melody-generator.ts` + Web Audio): sin red, sin GPU y sin créditos. Reglas para que sea fácil de tararear: rango de una octava, sobre todo grados conjuntos, estructura A A' y cierre en la tónica.

## Versiones producidas con IA (automático)

Con `HUMMING_AI_VERSIONS=True` (por defecto) y el endpoint de Modal configurado, **el tarareo entrega directamente sus versiones producidas con IA**, sin un paso aparte y sin costo extra (sigue siendo `HUMMING_CREDIT_COST`, 1 crédito):

1. Cada vez que el worker termina una versión (`version-N-lista`), Django crea una `HummingEnhancement` con `automatic=True` en el estilo que eligió el worker (`WORKER_PRESETS` en `styles.py`: pop, folk, balada, lofi, rock suave, épico, electrónico) y la manda a `CoverServer` (1 variante, fidelidad media).
2. Cada tarjeta muestra "Mejorando con IA…" y después la versión producida, con su portada. Se puede escuchar la que ya está mientras se producen las demás.
3. Al elegir, la `Song` usa el audio y la portada con IA. Las otras versiones con IA se borran de R2. Si la IA falló para esa versión, se usa la de FluidSynth.
4. `CoverServer` tiene `max_containers=2`: las 3 versiones se encolan en GPU ya encendidas en lugar de encender 3 en frío.

### Tiempos de respuesta (medidos 2026-11-19, `mi_tarareo.wav`)

| | Primera versión con IA | Las 3 con IA |
|---|---|---|
| Antes de optimizar, GPU fría | ~89 s | ~109 s |
| **GPU fría** | **55 s** | **76 s** |
| **GPU encendida** | **32 s** | **59 s** |

Optimizaciones aplicadas:

1. **Precalentar la GPU**: al subir el tarareo, Django llama a `warm_cover` (Modal) mediante la tarea `warm_ai_gpu`. El arranque en frío de `CoverServer` ocurre mientras el worker analiza. Variable: `MODAL_ENDPOINT_WARM_COVER`.
2. **Consultar a Modal cada 3 s** (`HUMMING_ENHANCE_POLL_INTERVAL_SECONDS`, antes 10).
3. **Cola propia de Celery** (`humming`, servicio `celery-humming` en `docker-compose.yml`): el tarareo no espera detrás de generaciones, stems o exportaciones.

4. **Versiones del worker en paralelo** (`TARAREO_VERSIONES_PARALELAS=3`): las alternativas se generan a la vez que la principal (la principal se sigue entregando primero). Medido con la GPU encendida: versiones del worker a los 24 / 29 / 34 s (antes 20 / 33 / 47 s).

Con la GPU encendida, las 3 con IA siguen en **~58 s**: ahora el cuello de botella es `CoverServer`, que atiende las versiones de a una (~9 s cada una). Para bajar más hay que producirlas en paralelo en la GPU (precalentar 2 contenedores o atender varias a la vez en uno), a cambio de más costo de GPU.

## Gráfico "Tu tarareo vs. la canción" y % de parecido

- **Gráfico** (`components/humming/melody-chart.tsx`): la altura real de la voz (línea, YIN cada 50 ms), las notas detectadas (barras naranjas) y la melodía ajustada al pulso que siguen las canciones (barras azules), con eje en notas y Hz al pasar el mouse o tocar. Arriba, qué % del tiempo la voz estuvo a menos de medio tono de esa melodía. Los datos vienen en `metadata.grafico` (el worker los escribe en `analisis.json`, así que ya están en los metadatos provisionales).
- **Parecido con tu melodía** (por versión con IA y por variante de "Mejorar con IA"): al completarse una versión, Celery llama a `POST {TARAREO_URL}/parecido` con URLs firmadas de `arreglo-N.mid` y de los audios. El worker transcribe cada audio con basic-pitch y mide qué parte de la melodía suena, descontando el azar (`gm_tarareo/app/pipeline/parecido.py`). Se guarda en `HummingEnhancement.variant_similarity` y se expone como `similarity: {puntaje, nivel}`. Llega ~6-13 s después del audio y no lo retrasa; si falla, la versión sigue disponible sin el %.
- **Cómo leerlo** (calibración 2026-11-19 con `mi_tarareo` y otro tarareo): FluidSynth contra sí misma 97 %; versiones con IA del mismo tarareo 40-56 % (fidelidad media/alta) y 21-33 % (libre); otra melodía en la misma tonalidad y tempo ≤ 10 %. Niveles: alto ≥ 38 %, medio ≥ 18 %, bajo debajo. Se descartó comparar croma del audio completo: mide tonalidad y armonía, no melodía.
- Variables: `HUMMING_SIMILARITY` (por defecto `True`), `HUMMING_SIMILARITY_TIMEOUT_SECONDS` (120).

## Mejorar con IA

Toma una versión del tarareo (el MP3 de FluidSynth ya en R2) y la rehace con **ACE-Step 1.5 en modo cover** (Modal, `CoverServer`, GPU A10G) en el estilo que elija el usuario, conservando la melodía.

Cada pedido genera **`HUMMING_ENHANCE_VARIANTS` variantes (3 por defecto) en una sola pasada** (`batch_size`, semillas distintas) con una portada SDXL-Turbo compartida, y cobra `HUMMING_ENHANCE_CREDIT_COST` por el lote. El usuario escucha las variantes A, B y C y elige una (`POST /api/humming/enhancements/{id}/choose/ {variant}`): esa se guarda como `Song` (`source_type='hummed'`, MP3 de 192 kbps) y las demás se borran de R2. Antes se usaba el *audio2audio* de ACE-Step v1, pero no cambiaba el estilo (ver `docs/evaluacion-fase4.md`).

```
POST /api/humming/{id}/enhance/ {version, style, custom_style?, fidelity}
  → reserva HUMMING_ENHANCE_CREDIT_COST créditos → Celery → Modal generate_from_reference
  → polling (HUMMING_ENHANCE_POLL_INTERVAL_SECONDS) → Song + cobro (o libera créditos si falla)
```

- **Estilos** (`apps/humming/styles.py`): 36 estilos en 4 grupos (populares, latinos, andinos y otros) o texto libre. Cada uno tiene tags en inglés para ACE-Step; se les suman el BPM y la tonalidad del tarareo. Los andinos están marcados como experimentales porque ACE-Step tiene pocos ejemplos de esos géneros.
- **Fidelidad** → `audio_cover_strength` de ACE-Step 1.5: alta 0.8 · media 0.5 · libre 0.2 (1.0 = muy fiel). Además se envían el BPM y la tonalidad del tarareo.
- **Modal**: el endpoint `generate_from_reference` de `gm_backend/ml/modal_music_server.py` despacha a `CoverServer` (ACE-Step 1.5 commit fijado, imagen propia porque pide torch 2.10). Solo acepta referencias bajo `humming/`. Los pesos se descargan solos la primera vez al Volume `ace-step-15-checkpoints`. Tras desplegar, copiar la URL del endpoint a `MODAL_ENDPOINT_FROM_REFERENCE`.
- **Tiempos medidos (3 variantes)**: ~24 s con el contenedor encendido y ~55-75 s en frío (carga ACE-Step 1.5 y SDXL). Con 1 variante, ~10 s.
- **Versión base automática**: el usuario elige solo el estilo. Cada estilo tiene en `base` los estilos del worker que mejor le sirven de punto de partida (por ejemplo, caporales → épico; bolero → balada; jazz → lo-fi), porque el modo cover conserva el ritmo y la estructura de la referencia. `pick_base_version` usa la primera que exista en el tarareo o, si no hay ninguna, la principal. `version` en `POST /enhance/` pasó a ser opcional.
- `GET /api/humming/styles/` devuelve el catálogo, el costo y si la mejora está disponible (sin endpoint configurado responde `available: false`).

## Siguientes pasos

- Probar la grabación con micrófono real en Chrome y Safari.
- Fase 4 (ML): RMVPE o torchcrepe en lugar de basic-pitch, LoRA de ACE-Step para géneros andinos y evaluación con CLAP.
