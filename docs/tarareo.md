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

## Siguientes fases

- **Fase 2**: página "Tararear" en React (grabar, progreso, elegir versión).
- **Fase 3**: "Mejorar con IA" — ACE-Step en Modal usando la versión de FluidSynth como referencia (audio2audio), con más estilos y cobro en créditos.
