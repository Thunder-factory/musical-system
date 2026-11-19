# Especificación — "Cambiar caras" (Face Swap) en videos cortos

> Estado: especificación para implementar. Rama `feature/faceswap`.
> Autor: Arquitecto / Spec Lead. Fecha: 2026-11-19.
> Patrón de referencia: **"Separar pistas"** (`apps/stems`, `apps/credits`, `ml/modal_client.py`,
> `ml/modal_demucs_server.py`, `apps/core/tasks.py`, `src/pages/stems/`).
> Pipeline de IA portado desde `/home/lmc/projects/faceswap/worker/` (solo lectura).

Esta spec se implementa **tal cual está escrita**. Si algo no cuadra con el código real, se
corrige la spec (y se avisa al orquestador) antes de improvisar.

---

## 0. Decisiones y choques de convenciones

| Tema | Decisión | Motivo |
|---|---|---|
| Estructura del frontend | Se usa la estructura **del repo** (`src/pages/<módulo>/`, `src/components/<módulo>/`, `src/api/modules/`, `src/hooks/`, `src/types/`), **no** `src/features/` | Choque con `React_Feature_Based.md`: manda el repo (`docs/estructura_frontend.md`). Para mantener la cohesión vertical, todo lo de la feature lleva el prefijo/carpeta `faceswap`. |
| Librería de UI | **No hay shadcn** en el repo. Se usa Tailwind + tokens CSS de `src/index.css` (`--color-primary`, `--bg-card`, …) + `lucide-react`, igual que `stems-page.tsx` | Choque con el Protocolo §7: manda el repo y `docs/ui-specification.md`. |
| `AGENTS.md` por paquete | **No se crean** | El repo no los usa; esta spec + `01_API_CONTRACT.md` cumplen ese papel. |
| Estilo del servidor Modal | Igual que `modal_demucs_server.py`: un solo endpoint HTTP `face_swap` con `requires_proxy_auth=True`, `action: "status"` para sondear, entrada/salida en **R2** vía Secret `music-gen-secret`, controlador CPU que hace `spawn` de una clase GPU y guarda el estado en un `modal.Dict` propio | Es exactamente lo que hace Demucs en el repo. Lo que **no** se copia del proyecto faceswap: el Volume `faceswap-data` para entradas/salidas, ni que el backend llame `Function.from_name(...).spawn()` por SDK. El único Volume es el de **pesos de modelos** (cache). |
| App de Modal | Se registra en la app compartida `gm-music-server` (`from .modal_app import app`) y se **importa desde `modal_music_server.py`** (igual que Demucs) | El deploy del repo es `modal deploy ml/modal_music_server.py`. Si se desplegara `modal_faceswap_server.py` solo, la app quedaría sin las funciones de música/stems. |
| Marca de agua | **NO**. Se elimina `add_watermark`; se conserva solo el remux de audio a AAC + `+faststart` | Requisito. |
| Créditos | 3 créditos (`FACESWAP_CREDIT_COST`), `reference_type='faceswap_job'`: reservar al crear, confirmar al completar, liberar si falla | Igual que stems. |
| Concurrencia | **1 job activo por usuario** (constraint parcial en BD), 409 si ya hay uno | Más simple que el hash de stems y acota el gasto de GPU. |
| Fotos y clips subidos | Se **borran de R2** cuando el job llega a estado final; solo se conserva el resultado | Privacidad (caras). |
| Estilo Python | `pyproject.toml` manda: línea ≤ 100 (CONTRIBUTING dice 88; Black/ruff del repo usan 100). Docstring en toda función pública. Lógica en `services/`, views delgadas. | Convención del repo. |

---

## 1. Resumen y flujo extremo a extremo

El usuario autenticado sube una **foto de su cara** y elige un **video base**: una plantilla del
catálogo (lo administra el admin) o un clip propio de ≤ 15 s. Acepta el consentimiento, paga 3
créditos (reserva) y recibe un MP4 con su cara. Puede verlo, descargarlo y borrarlo.

```text
[React /faceswap]                      [Django API]                         [Celery]                 [Modal gm-music-server]           [R2]
     │ GET /api/faceswap/templates/ ─────▶ lista plantillas activas + URLs firmadas ◀──────────────────────────────────────────── thumbnails/previews
     │ POST /api/faceswap/jobs/ (multipart: photo, template_id | video, consent)
     │──────────────────────────────────▶ faceswap_service.request_face_swap()
     │                                     1. valida foto (Pillow) / clip (ffprobe ≤15 s)
     │                                     2. lock user → 409 si hay job activo
     │                                     3. reserve_credits(3, 'faceswap_job') → 402 si no alcanza
     │                                     4. crea FaceSwapJob(queued)
     │                                     5. sube foto (+ clip) ───────────────────────────────────────────────────────▶ faceswap/uploads/...
     │                                     6. process_faceswap_job.delay(job_id)
     │◀── 201 {job_id, status:"queued"}           │
     │                                            ▼
     │                                     process_faceswap_job ── POST {async:true, client_job_id, photo_s3_key,
     │                                            │                 video_s3_key, ref_time_s} ─▶ face_swap (CPU) → claim + spawn
     │                                            │◀──────────────── {remote_job_id, status, progress_pct}      │
     │                                            ▼                                                             ▼
     │                                     poll_faceswap_job (cada 5 s) ── POST {action:"status"} ─▶ Dict    FaceSwapServer.process (GPU T4)
     │ GET /api/faceswap/jobs/{id}/ (cada 4 s)    │◀── {status, progress_pct, output_s3_key?}                 descarga foto+video ◀── R2
     │◀── {status, progress_pct}                  │                                                         normaliza → FaceFusion → remux AAC
     │                                            │  completed: head_object(output) → confirm_reservation       sube resultado ──────▶ faceswap/results/<rid>.mp4
     │                                            │  → completed/100 % → borra foto y clip de R2 → notify_user
     │                                            │  failed/timeout: release_reservation → failed → borra foto y clip
     │ GET /api/faceswap/jobs/{id}/result-url/ ──▶ {url} firmada (video/mp4; ?download=1 → attachment)
     │ DELETE /api/faceswap/jobs/{id}/ ──────────▶ soft delete + borra resultado de R2 (409 si activo)

core.tasks.recover_abandoned_operations: jobs atascados → reencola (reserva válida) o falla y libera.
```

Estados del job: `queued → processing → completed | failed`. (Mismos literales que `StemJob`.)

---

## 2. Base de datos (DB-first)

App nueva: `gm_backend/apps/faceswap/` (registrar `'apps.faceswap'` en `INSTALLED_APPS` justo
después de `'apps.stems'`). Ambos modelos heredan de `apps.core.models.BaseModel`
(UUID `id`, `created_at`, `updated_at`, `deleted_at` + `soft_delete()`).

### 2.1 `FaceSwapTemplate` (catálogo administrado)

| Campo | Tipo Django | Notas |
|---|---|---|
| `title` | `CharField(max_length=120)` | obligatorio |
| `video_s3_key` | `TextField()` | `faceswap/templates/videos/<uuid>.<ext>` |
| `thumbnail_s3_key` | `TextField()` | `faceswap/templates/thumbnails/<uuid>.jpg` (subida o generada con ffmpeg) |
| `duration_seconds` | `FloatField()` | ffprobe al subir |
| `ref_time_s` | `FloatField(null=True, blank=True)` | segundo donde se ve sola la cara a reemplazar. `null` → modo "cara más grande" |
| `is_active` | `BooleanField(default=True)` | solo las activas se muestran al usuario |

```python
class Meta:
    ordering = ['-created_at']
    constraints = [
        models.CheckConstraint(
            check=models.Q(ref_time_s__isnull=True) | models.Q(ref_time_s__gte=0),
            name='faceswap_template_ref_time_non_negative',
        ),
    ]
```

Borrado = **soft delete** (`deleted_at` + `is_active=False`); nunca se borra la fila ni sus
objetos R2 (los jobs la referencian con `PROTECT`).

### 2.2 `FaceSwapJob` (copia los campos de `StemJob`)

| Campo | Tipo Django | Notas |
|---|---|---|
| `user` | `ForeignKey(AUTH_USER_MODEL, CASCADE, related_name='faceswap_jobs')` | |
| `source_type` | `CharField(max_length=10, choices=[('template','Template'),('upload','Upload')])` | |
| `template` | `ForeignKey(FaceSwapTemplate, PROTECT, null=True, blank=True, related_name='jobs')` | obligatorio si `source_type='template'` |
| `photo_s3_key` | `TextField(null=True, blank=True)` | `faceswap/uploads/photos/<uuid>.<ext>`; se pone `NULL` tras borrarla |
| `source_video_s3_key` | `TextField(null=True, blank=True)` | snapshot: clave de la plantilla o del clip subido (`faceswap/uploads/videos/<uuid>.<ext>`). Si era `upload`, se borra de R2 y queda `NULL` al terminar |
| `source_video_filename` | `CharField(max_length=255, blank=True, default='')` | nombre original del clip; en plantilla = título de la plantilla |
| `source_duration_seconds` | `FloatField(null=True, blank=True)` | |
| `ref_time_s` | `FloatField(null=True, blank=True)` | snapshot de la plantilla; `NULL` para clips propios |
| `output_s3_key` | `TextField(null=True, blank=True)` | `faceswap/results/<remote_job_id>.mp4` (lo devuelve Modal) |
| `output_file_size_bytes` | `BigIntegerField(null=True, blank=True)` | de `head_object` |
| `remote_job_id` | `CharField(max_length=255, null=True, blank=True, unique=True)` | |
| `model_used` | `CharField(max_length=60, default='facefusion-inswapper_128_fp16')` | |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default='queued')` | `queued`, `processing`, `completed`, `failed` |
| `progress_pct` | `IntegerField(default=0)` | 0-100 |
| `error_message` | `TextField(null=True, blank=True)` | |
| `credits_used` | `IntegerField(default=0)` | 3 al completar |
| `started_at` / `completed_at` | `DateTimeField(null=True, blank=True)` | |

```python
class Meta:
    ordering = ['-created_at']
    indexes = [
        models.Index(fields=['user', '-created_at'], name='faceswap_job_user_created'),
        models.Index(fields=['status', 'updated_at'], name='faceswap_job_status_upd'),
    ]
    constraints = [
        models.UniqueConstraint(
            fields=['user'],
            condition=models.Q(status__in=['queued', 'processing']),
            name='unique_active_faceswap_job',
        ),
        models.CheckConstraint(
            check=(
                models.Q(source_type='template', template__isnull=False)
                | models.Q(source_type='upload', template__isnull=True)
            ),
            name='faceswap_job_source_consistent',
        ),
    ]
```

Notas:
- `deleted_at` (de `BaseModel`) = borrado lógico del job por el usuario. Todas las queries de
  usuario filtran `deleted_at__isnull=True`.
- No hay tabla de archivos resultantes (a diferencia de `StemFile`): un job = un MP4.
- Migración: `apps/faceswap/migrations/0001_initial.py` generada con `makemigrations faceswap`.

### 2.3 Cambio menor en `apps/notifications`

- `Notification.TYPE_CHOICES`: agregar `('faceswap_ready', 'Face swap listo')`.
- `services._DEFAULTS`: `'faceswap_ready': ('Tu video está listo', 'Ya puedes verlo en Cambiar caras.')`.
- Migración `AlterField` generada con `makemigrations notifications`.

---

## 3. Endpoints REST

Prefijo `/api/faceswap/` (`config/urls.py`: `path('api/faceswap/', include('apps.faceswap.urls'))`).
JWT obligatorio en todos. Formato de error **igual que stems**: `{"error": "<mensaje en español>"}`.
Permisos admin: `[IsAuthenticated, IsAdmin]` de `apps.core.permissions`.

### 3.1 Tabla resumen

| Método | Ruta | Permiso | Request | Response OK | Errores |
|---|---|---|---|---|---|
| GET | `/api/faceswap/templates/` | usuario | — | 200 `Template[]` (activas, no borradas) | — |
| POST | `/api/faceswap/jobs/` | usuario | multipart `photo`, `consent`, (`template_id` \| `video`) | 201 `{job_id, status}` | 400, 402, 404, 409, 500 |
| GET | `/api/faceswap/jobs/` | usuario | — | 200 `Job[]` propios, más nuevos primero | — |
| GET | `/api/faceswap/jobs/{id}/` | usuario (dueño) | — | 200 `Job` | 404 |
| DELETE | `/api/faceswap/jobs/{id}/` | usuario (dueño) | — | 204 | 404, 409 si está `queued`/`processing` |
| GET | `/api/faceswap/jobs/{id}/result-url/` | usuario (dueño) | `?download=1` opcional | 200 `{url}` | 404, 409 si no está `completed` |
| GET | `/api/faceswap/admin/templates/` | admin | — | 200 `AdminTemplate[]` (incluye inactivas, no borradas) | 403 |
| POST | `/api/faceswap/admin/templates/` | admin | multipart `title`, `video`, `thumbnail?`, `ref_time_s?`, `is_active?` | 201 `AdminTemplate` | 400, 403 |
| PATCH | `/api/faceswap/admin/templates/{id}/` | admin | multipart o JSON: `title?`, `ref_time_s?` (`""`/`null` lo borra), `is_active?`, `thumbnail?` | 200 `AdminTemplate` | 400, 403, 404 |
| DELETE | `/api/faceswap/admin/templates/{id}/` | admin | — | 204 (soft delete) | 403, 404 |

El video de una plantilla **no se reemplaza** (se crea otra y se desactiva la vieja).

### 3.2 `urls.py`

```python
urlpatterns = [
    path('templates/', TemplateListView.as_view(), name='faceswap-templates'),
    path('jobs/', FaceSwapJobListCreateView.as_view(), name='faceswap-jobs'),
    path('jobs/<uuid:id>/', FaceSwapJobDetailView.as_view(), name='faceswap-job-detail'),
    path('jobs/<uuid:id>/result-url/', FaceSwapResultUrlView.as_view(), name='faceswap-result-url'),
    path('admin/templates/', AdminTemplateListCreateView.as_view(), name='faceswap-admin-templates'),
    path('admin/templates/<uuid:id>/', AdminTemplateDetailView.as_view(), name='faceswap-admin-template'),
]
```

### 3.3 Ejemplos JSON

**`Template`** (GET `/templates/`). URLs firmadas de R2 con 1 h de vida (`generate_presigned_url`):

```json
[
  {
    "id": "0b6a3f0e-6f0a-4c51-9a55-2f0e8f6d1a11",
    "title": "Oficina — diario",
    "duration_seconds": 8.4,
    "has_reference": true,
    "thumbnail_url": "https://<r2>/faceswap/templates/thumbnails/....jpg?X-Amz-...",
    "preview_url": "https://<r2>/faceswap/templates/videos/....mp4?X-Amz-..."
  }
]
```

**`AdminTemplate`** = `Template` + `ref_time_s`, `is_active`, `created_at`, `updated_at`:

```json
{
  "id": "0b6a3f0e-6f0a-4c51-9a55-2f0e8f6d1a11",
  "title": "Oficina — diario",
  "duration_seconds": 8.4,
  "has_reference": true,
  "ref_time_s": 2.5,
  "is_active": true,
  "thumbnail_url": "https://...",
  "preview_url": "https://...",
  "created_at": "2026-11-19T15:02:11Z",
  "updated_at": "2026-11-19T15:02:11Z"
}
```

**POST `/jobs/`** — multipart:

| Campo | Tipo | Regla |
|---|---|---|
| `photo` | archivo | obligatorio |
| `consent` | `"true"` | obligatorio; cualquier otro valor → 400 |
| `template_id` | UUID | exclusivo con `video` |
| `video` | archivo | exclusivo con `template_id` |

```json
{ "job_id": "5d0b2c55-8a4e-4f0a-9d0e-7c1b9a3e2f10", "status": "queued" }
```

**`Job`** (GET `/jobs/`, GET `/jobs/{id}/`):

```json
{
  "id": "5d0b2c55-8a4e-4f0a-9d0e-7c1b9a3e2f10",
  "source_type": "template",
  "template": { "id": "0b6a3f0e-6f0a-4c51-9a55-2f0e8f6d1a11", "title": "Oficina — diario" },
  "source_video_filename": "Oficina — diario",
  "source_duration_seconds": 8.4,
  "model_used": "facefusion-inswapper_128_fp16",
  "remote_job_id": "9f1c...",
  "status": "processing",
  "progress_pct": 47,
  "credits_used": 0,
  "error_message": null,
  "has_result": false,
  "created_at": "2026-11-19T15:10:00Z",
  "started_at": "2026-11-19T15:10:02Z",
  "completed_at": null
}
```

`has_result = status == 'completed' and output_s3_key is not None`. Para `upload`, `template` es
`null` y `source_video_filename` es el nombre del clip.

**GET `/jobs/{id}/result-url/`** → `{"url": "https://..."}`. Siempre `response_content_type='video/mp4'`;
con `?download=1`: `response_content_disposition='attachment; filename="faceswap-<8 primeros del id>.mp4"'`.

**Errores** (siempre `{"error": "..."}`):

| Código | Caso | Mensaje |
|---|---|---|
| 400 | sin foto | `Debes subir una foto de tu cara.` |
| 400 | consentimiento | `Debes confirmar que la foto es tuya o tienes permiso.` |
| 400 | 0 o 2 fuentes | `Elige una plantilla o sube un clip, no ambos.` |
| 400 | foto inválida | ver §4 |
| 400 | clip inválido / > 15 s / > 50 MB | ver §4 |
| 402 | créditos | `Sin créditos suficientes.` (el mensaje de `InsufficientCreditsError`) |
| 404 | plantilla inexistente, borrada o inactiva | `La plantilla no existe o no está disponible.` |
| 404 | job ajeno o inexistente | `Job not found` (igual que stems) |
| 409 | job activo al crear | `Ya tienes un video en proceso. Espera a que termine.` |
| 409 | borrar job activo | `No puedes borrar un video que se está procesando.` |
| 409 | result-url sin resultado | `El video todavía no está listo.` |
| 500 | R2/Redis caído | `{"error": str(e)}` (igual que stems) |

### 3.4 Capas (CONTRIBUTING: lógica en services)

- `serializers.py`: `TemplateSerializer`, `AdminTemplateSerializer` (URLs vía
  `SerializerMethodField` → `generate_presigned_url`), `AdminTemplateWriteSerializer`
  (`title`, `ref_time_s`, `is_active`; valida tipos), `FaceSwapJobSerializer`
  (`template` como `{id,title}`, `has_result`).
- `services/faceswap_service.py`: `request_face_swap(...)`, `delete_job(user, job_id)`,
  excepciones `PhotoValidationError`, `VideoValidationError`, `ActiveJobError`,
  `TemplateUnavailableError`, `JobNotDeletableError`; reexporta `InsufficientCreditsError` de
  credits (igual que stems).
- `services/media_validation.py`: `validate_photo(file) -> str` (extensión) y
  `validate_video(file, *, max_seconds) -> float` (duración), `extract_thumbnail(video_path, at_s) -> Path`.
- `services/template_service.py`: `create_template(...)`, `update_template(...)`, `soft_delete_template(...)`.
- `views.py`: cada método ≤ ~15 líneas: obtiene datos → llama al service → mapea excepción a código.

---

## 4. Validaciones

Todas en backend (el frontend repite las baratas solo para UX).

### 4.1 Foto (`validate_photo`)
1. Extensión en `{.jpg, .jpeg, .png, .webp}` → si no: `Solo se aceptan fotos JPG, PNG o WEBP.`
2. `0 < size ≤ settings.FACESWAP_MAX_PHOTO_BYTES` (8 MB) → `La foto está vacía.` /
   `La foto excede el límite de 8 MB.`
3. Pillow (`pillow==12.2.0` ya está en requirements): `Image.open(file)`, `verify()`, reabrir y leer
   `size`; `file.seek(0)` siempre al final. Error → `El archivo no es una imagen válida.`
4. Lado menor ≥ 128 px → `La foto es muy pequeña (mínimo 128×128 px).`

No se detecta la cara en backend (no hay modelo); si FaceFusion no la encuentra, el job falla
en Modal con mensaje claro y se liberan los créditos.

### 4.2 Clip propio y video de plantilla (`validate_video`)
1. Extensión en `{.mp4, .mov, .webm}` → `Solo se aceptan videos MP4, MOV o WEBM.`
2. `0 < size ≤ settings.FACESWAP_MAX_VIDEO_BYTES` (50 MB) → `El video excede el límite de 50 MB.`
3. Copiar a `NamedTemporaryFile(suffix=ext)` por `chunks()` (como `validate_audio_file`) y correr:
   ```text
   ffprobe -v error -select_streams v:0 -show_entries stream=width,height:format=duration -of json <tmp>
   ```
   - `FileNotFoundError` / `CalledProcessError` / sin `streams` → `El archivo no contiene video decodificable.`
   - `duration <= 0` → `No se pudo determinar la duración del video.`
   - `duration > settings.FACESWAP_MAX_SECONDS + 0.5` → `El video debe durar como máximo 15 segundos.`
     (0,5 s de tolerancia por redondeo del contenedor; Modal además recorta con `-t 15`).
4. `file.seek(0)` antes de devolver la duración.

### 4.3 Plantilla (admin)
- `title` 1-120 caracteres.
- `video` con las reglas de 4.2.
- `ref_time_s`: vacío/`null` o número `0 ≤ ref_time_s ≤ duration_seconds` → `El segundo de referencia está fuera del video.`
- `thumbnail` opcional (reglas de 4.1 pero tope 2 MB). Si falta: `extract_thumbnail` con
  `ffmpeg -v error -y -ss <ref_time_s or min(1, duration/2)> -i <tmp> -frames:v 1 -vf scale=-2:360 <out.jpg>`
  y se sube con `ml.storage_client.upload_file`.

### 4.4 Reglas de negocio al crear el job
1. Exactamente una fuente y `consent == "true"` (antes de tocar archivos).
2. Validar foto y (si hay) clip **antes** de reservar créditos.
3. Plantilla: `FaceSwapTemplate.objects.get(id=..., is_active=True, deleted_at__isnull=True)`.
4. En `transaction.atomic()` con `select_for_update()` del usuario:
   - Si hay job activo: si no tiene `photo_s3_key` y su `created_at` es más viejo que
     `FACESWAP_REMOTE_TIMEOUT_SECONDS` → se marca `failed` (`La subida quedó abandonada.`) y se libera
     su reserva (mismo criterio que stems); si no → `ActiveJobError` (409).
   - `reserve_credits(user, amount=settings.FACESWAP_CREDIT_COST, reference_id=str(job_id), reference_type='faceswap_job')`
     → `InsufficientCreditsError` (402).
   - Crear `FaceSwapJob(status='queued', ...)`. `IntegrityError` por la constraint → liberar reserva y `ActiveJobError`.
5. Fuera de la transacción: `upload_fileobj(photo, folder='faceswap/uploads/photos')`, y si es
   `upload`, `upload_fileobj(video, folder='faceswap/uploads/videos')`; guardar claves y
   `process_faceswap_job.delay(str(job.id))`. Ante cualquier excepción: job `failed`
   (`No se pudo subir los archivos.`), `release_reservation`, borrar las claves ya subidas
   (best effort) y relanzar (la view responde 500).

---

## 5. Celery, recuperación y settings

### 5.1 `apps/faceswap/tasks.py` (copia de `apps/stems/tasks.py` con estos cambios)

| Función | Comportamiento |
|---|---|
| `_schedule_faceswap_poll(job_id, countdown=settings.FACESWAP_POLL_INTERVAL_SECONDS)` | `poll_faceswap_job.apply_async(args=[job_id], countdown=countdown)` |
| `_cleanup_inputs(job_id)` | best effort: borra de R2 `photo_s3_key` y, si `source_type='upload'`, `source_video_s3_key`; pone ambas en `NULL`. Nunca borra el video de una plantilla. Nunca lanza. |
| `_mark_faceswap_failed(job_id, message, progress=None)` | igual que `_mark_stem_failed` (`reference_type='faceswap_job'`) + `_cleanup_inputs` |
| `_validate_output_object(key) -> int` | `key` str no vacía que empieza por `faceswap/results/`; `head_object` con `ContentLength > 0`; devuelve el tamaño |
| `_settle_faceswap_credits(job)` | reserva `reserved` → `confirm_reservation`; `confirmed` → no hace nada (idempotente); `released` o inexistente → `ValueError('La reserva de créditos fue liberada.')`. **Sin** el fallback legacy `deduct_credits` de stems (no hay jobs legacy). |
| `process_faceswap_job` (`bind=True, max_retries=3`) | si final → return; si tiene `remote_job_id` → poll inmediato; si no: `submit_faceswap_job(settings.MODAL_ENDPOINT_FACESWAP, {client_job_id, photo_s3_key, video_s3_key, ref_time_s})`, guarda `remote_job_id`, `started_at`, poll con `countdown=0`. Reintento 10 s; al agotar → `_mark_faceswap_failed`. |
| `recover_faceswap_job(job_id)` | igual que `recover_stem_job` |
| `poll_faceswap_job` (`bind=True, max_retries=5`) | igual que `poll_stem_job` con: timeout `FACESWAP_REMOTE_TIMEOUT_SECONDS` (`La generación excedió el tiempo máximo permitido.`); `queued/processing` → actualizar y reprogramar; `failed` → `_mark_faceswap_failed(remote.error_message or 'Modal no pudo procesar el video.')`; `completed` → `_validate_output_object(remote['output_s3_key'])`; en `transaction.atomic()` + `select_for_update`: `_settle_faceswap_credits`, `output_s3_key`, `output_file_size_bytes`, `status='completed'`, `progress_pct=100`, `credits_used=settings.FACESWAP_CREDIT_COST`, `completed_at`. Después del commit: `_cleanup_inputs` y `notify_user(job.user, type='faceswap_ready', reference_id=str(job.id))` en try/except. |

**Cobro idempotente**: el doble bloqueo (`status in FINAL` releído bajo `select_for_update`) +
`confirm_reservation` idempotente + unique `(user, reference_id, reference_type)` de
`CreditReservation` garantizan **un solo** `CreditTransaction` aunque dos polls lleguen a la vez.

### 5.2 `ml/modal_client.py` (solo agregar, no refactorizar)

```python
def submit_faceswap_job(endpoint_url: str, body: dict) -> dict:
    """Envía un face swap asíncrono y retorna su remote_job_id."""
    # idéntico a submit_stem_job: {**body, "async": True}, MODAL_SUBMIT_READ_TIMEOUT_SECONDS,
    # MODAL_REQUEST_RETRIES; exige data["remote_job_id"].

def get_faceswap_job_status(endpoint_url: str, remote_job_id: str) -> dict:
    """Consulta el estado de un face swap remoto sin iniciar otra ejecución."""
    # idéntico a get_stem_job_status; exige "status" y "progress_pct".
```

### 5.3 `apps/core/tasks.py`

- `_remote_state`: nueva rama `kind == 'faceswap'` → `get_faceswap_job_status(settings.MODAL_ENDPOINT_FACESWAP, remote_job_id)`.
- `recover_abandoned_operations`: agregar `'faceswap': 0` al dict y un bloque calcado del de
  `StemJob` con `FaceSwapJob`, `_stale('FACESWAP_REMOTE_TIMEOUT_SECONDS')`,
  `reference_type='faceswap_job'`, `enqueue` → `apps.faceswap.tasks.recover_faceswap_job.delay`,
  `failure_message='El face swap abandonado no tiene una reserva confirmable.'`,
  `final_statuses={'completed', 'failed'}`, `cleanup_failed=lambda job_id=...: _cleanup_inputs(job_id)`
  (importado perezosamente). Filtrar también `deleted_at__isnull=True`.

> **Hallazgo:** `recover_abandoned_operations` **no está** en `app.conf.beat_schedule`
> (`workers/celery.py` solo agenda `generate-auto-playlists-daily`). El seguimiento normal no
> depende de Beat (los polls se reprograman solos con `apply_async`). Esta feature **no** agrega
> la entrada a Beat porque cambiaría el comportamiento de stems/karaoke/mix del equipo; queda
> anotado como riesgo (§10) para que lo decida el equipo.

### 5.4 Settings (`config/settings.py`, junto a las de stems) y `.env.example` (sección 8)

```python
MODAL_ENDPOINT_FACESWAP = config('MODAL_ENDPOINT_FACESWAP', default='')
FACESWAP_CREDIT_COST = config('FACESWAP_CREDIT_COST', cast=int, default=3)
FACESWAP_MAX_SECONDS = config('FACESWAP_MAX_SECONDS', cast=int, default=15)
FACESWAP_MAX_PHOTO_BYTES = config('FACESWAP_MAX_PHOTO_BYTES', cast=int, default=8 * 1024 * 1024)
FACESWAP_MAX_VIDEO_BYTES = config('FACESWAP_MAX_VIDEO_BYTES', cast=int, default=50 * 1024 * 1024)
FACESWAP_REMOTE_TIMEOUT_SECONDS = config('FACESWAP_REMOTE_TIMEOUT_SECONDS', cast=int, default=1200)
FACESWAP_POLL_INTERVAL_SECONDS = config('FACESWAP_POLL_INTERVAL_SECONDS', cast=int, default=5)
```

Un **solo** endpoint (`MODAL_ENDPOINT_FACESWAP`), porque el patrón real de Demucs usa la misma URL
para submit y status (`action: "status"`). No existen `_SUBMIT`/`_STATUS` separados.

`.env.example` (sección 8, debajo de `MODAL_ENDPOINT_SEPARATE_STEMS=` y de las `DEMUCS_*`):

```text
MODAL_ENDPOINT_FACESWAP=
FACESWAP_CREDIT_COST=3
FACESWAP_MAX_SECONDS=15
FACESWAP_MAX_PHOTO_BYTES=8388608
FACESWAP_MAX_VIDEO_BYTES=52428800
FACESWAP_REMOTE_TIMEOUT_SECONDS=1200
FACESWAP_POLL_INTERVAL_SECONDS=5
FACESWAP_GPU=T4
FACESWAP_JOB_TTL_SECONDS=3600
FACESWAP_SPAWN_LEASE_SECONDS=300
```

(Las tres últimas las lee el contenedor de Modal con `os.environ.get(..., default)`, igual que
`DEMUCS_*`; como el Secret se crea solo con `^R2_`, en la práctica se usan los defaults.)

La reserva de créditos usa el `expires_in_seconds=3600` por defecto: es mayor que el timeout
remoto (1200 s) más la cola, igual que la relación stems 3600/1800.

---

## 6. Contrato del servidor Modal — `gm_backend/ml/modal_faceswap_server.py`

### 6.1 Estructura (espejo de `modal_demucs_server.py`)

```python
try:
    from .modal_app import app
except ImportError:
    from modal_app import app

controller_image = modal.Image.debian_slim().pip_install("fastapi[standard]", "boto3", "pydantic") \
    .add_local_file(<modal_app.py>, remote_path="/root/modal_app.py")

faceswap_image = (
    modal.Image.from_registry("nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04", add_python="3.12")
    .apt_install("ffmpeg", "git", "curl")             # sin fonts-dejavu: ya no hay drawtext
    .pip_install(<mismas versiones fijadas que faceswap/worker/modal_app.py>, "boto3")
    .run_commands(
        "git clone --depth 1 --branch 3.9.2 https://github.com/facefusion/facefusion.git /facefusion",
        # parche cuDNN para la T4 (copiar tal cual, con su comentario)
        "sed -i \"s/'GeForce GTX 1660')/'GeForce GTX 1660', 'Tesla T4')/\" /facefusion/facefusion/execution.py",
        "grep -q \"'Tesla T4'\" /facefusion/facefusion/execution.py",
    )
    .add_local_file(<modal_app.py>, remote_path="/root/modal_app.py")
)

music_gen_secrets = modal.Secret.from_name("music-gen-secret")
faceswap_job_status = modal.Dict.from_name("gm-faceswap-job-status", create_if_missing=True)
faceswap_models = modal.Volume.from_name("gm-faceswap-models", create_if_missing=True)

FACEFUSION_DIR = "/facefusion"
TARGET_FPS = 25
MAX_SECONDS = 15
MAX_HEIGHT = 720
GPU_CONFIG = os.environ.get("FACESWAP_GPU", "T4")
JOB_TTL_SECONDS / SPAWN_LEASE_SECONDS / PROCESSING_STALE_SECONDS  # FACESWAP_* (defaults 3600/300/1200)
```

Helpers **copiados de Demucs** cambiando `stem_job_status` → `faceswap_job_status` y
`DemucsServer` → `FaceSwapServer`: `_now`, `_get_r2_storage`, `_set_status`, `_status`,
`_validate_key`, `_claim_job`, `_ensure_job_status`, `_spawn_if_needed`, `_worker_owns_job`,
`_worker_can_fail_job`. El estado inicial usa `"output_s3_key": None` en vez de `"stems": {}`.
No se refactoriza Demucs para compartirlos (no tocar código del equipo).

```python
@app.cls(image=faceswap_image, gpu=GPU_CONFIG, secrets=[music_gen_secrets],
         volumes={"/facefusion/.assets": faceswap_models},
         timeout=900, scaledown_window=120, max_containers=2)
class FaceSwapServer:
    @modal.method()
    def process(self, request: dict, job_id: str, lease_id: str | None = None): ...

@app.function(image=controller_image, secrets=[music_gen_secrets], timeout=120)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def face_swap(request: dict): ...
```

`modal_music_server.py` agrega, en sus dos ramas de import (relativa y absoluta), debajo de la
de Demucs:

```python
from .modal_faceswap_server import FaceSwapServer, face_swap  # noqa: F401
```

### 6.2 Endpoint `face_swap` — submit

Request (lo arma `process_faceswap_job`; `submit_faceswap_job` agrega `async: true`):

```json
{
  "async": true,
  "client_job_id": "5d0b2c55-8a4e-4f0a-9d0e-7c1b9a3e2f10",
  "photo_s3_key": "faceswap/uploads/photos/1f3e....jpg",
  "video_s3_key": "faceswap/templates/videos/0b6a....mp4",
  "ref_time_s": 2.5
}
```

Reglas: `_validate_key` para ambas claves; `ref_time_s` es `null` o número `0 ≤ x ≤ 15`
(si no → `{"status":"failed","progress_pct":0,"error_message":"ref_time_s no es válido."}`);
sin `async: true` → `failed` con `La ejecución síncrona está deshabilitada; use async=true.`
(**no** se porta el modo síncrono legado de Demucs). Con `async`:
`_claim_job(client_job_id)` → `_spawn_if_needed(request, job_id)` → respuesta:

```json
{ "remote_job_id": "9f1c2d...", "status": "queued", "progress_pct": 0 }
```

### 6.3 Endpoint `face_swap` — status

Request: `{"action": "status", "remote_job_id": "9f1c2d..."}`. Response (valor del Dict):

```json
{ "status": "processing", "progress_pct": 47, "output_s3_key": null, "error_message": null,
  "device": "Tesla T4", "updated_at": 1763565000, "expires_at": 1763568600 }
```

Completado:

```json
{ "status": "completed", "progress_pct": 100,
  "output_s3_key": "faceswap/results/9f1c2d....mp4", "error_message": null,
  "timings": { "normalize": 3.1, "facefusion": 121.4, "remux": 1.2 } }
```

Fallo / no encontrado: `{"status":"failed","progress_pct":0,"error_message":"..."}`
(`Falta remote_job_id`, `Job remoto no encontrado o expirado`, o el error del worker ≤ 500 chars).

### 6.4 `FaceSwapServer.process` (flujo)

1. Leases idénticos a `DemucsServer.process` (spawn lease → worker lease con `skip_if_exists`).
2. `_set_status(processing, progress_pct=2, device=<cuda name>)` vía `onnxruntime.get_device()`
   o `nvidia-smi --query-gpu=name --format=csv,noheader` (no hay torch en la imagen).
3. En `tempfile.TemporaryDirectory(prefix=f"faceswap-{job_id}-")`: descargar de R2
   `photo_s3_key` → `source<ext>` y `video_s3_key` → `target<ext>`; validar tamaños > 0. `progress 5`.
4. `normalize_video(target, norm.mp4)` (portado tal cual: `-t 15`, `scale=-2:'min(720,ih)',fps=25`,
   x264 veryfast crf 18, AAC 128k). `progress 10`.
5. `run_facefusion(photo, norm, swapped, ref_time_s, on_progress)` portado tal cual:
   `headless-run`, `face_swapper` + `face_enhancer`, `inswapper_128_fp16`, pixel boost `256x256`,
   weight `1.0`, `codeformer` blend `45`, `--execution-providers cuda`, calidad 90; selector
   `reference` con `--reference-frame-number int(ref_time_s*25)` y `--reference-face-position 0`
   si hay `ref_time_s`, si no `one` + `--face-selector-order large-small`. `_run_streaming` portado
   (separa por `\r`/`\n`, parsea `processing: NN%`). Mapeo de progreso: `10 + pct * 80 // 100`,
   publicado como mucho cada 5 puntos. Separar la construcción del comando en
   `_facefusion_command(...) -> list[str]` (testeable sin GPU).
6. Si `swapped.mp4` no existe → `RuntimeError("No se detectó una cara en la foto o en el video.")`.
7. `finalize_video(swapped, final.mp4)` = `add_watermark` **sin** `-vf drawtext`:
   `ffmpeg -y -v error -i swapped.mp4 -map 0:v:0 -map 0:a:0? -c:v copy -c:a aac -b:a 128k -movflags +faststart final.mp4`
   (audio a AAC porque FaceFusion deja FLAC y Safari/iOS no lo reproduce). `progress 95`.
8. Subir a R2 `faceswap/results/{job_id}.mp4` (`ExtraArgs={"ContentType": "video/mp4"}`).
9. `faceswap_models.commit()` (cachea pesos descargados por FaceFusion).
10. Si perdió el worker lease → borrar el resultado y salir (como Demucs). Si no →
    `_set_status(completed, progress_pct=100, output_s3_key=..., timings=...)`.
11. `except`: si `_worker_can_fail_job` → borrar resultado parcial y `_set_status(failed, error_message=str(exc)[:500])`; relanzar.
    `finally`: liberar leases propios.

El worker **no** borra la foto ni el clip: el dueño de las entradas es Django (§5.1 `_cleanup_inputs`).

### 6.5 Qué se porta y qué no de `faceswap/worker`

| Se porta | No se porta |
|---|---|
| Imagen CUDA + deps fijadas + clon FaceFusion 3.9.2 + parche T4 | App `faceswap-worker`, Volume `faceswap-data`, Dict `faceswap-progress` |
| `normalize_video`, `run_facefusion`, `_run_streaming`, `PROGRESS_RE`, `DEFAULT_OPTS` (B) | `add_watermark` (drawtext) y `fonts-dejavu-core` |
| Volume de modelos (renombrado `gm-faceswap-models`) + `commit()` | `swap_bytes`, `smoke`, `compare`, `VARIANTS` |
| `max_containers=2`, `timeout=900`, GPU T4 | Lectura/escritura en Volume y `Function.from_name(...).spawn` desde el backend |

---

## 7. Frontend

### 7.1 Rutas y navegación (cero páginas huérfanas)

| Ruta | Layout / guard | Página | Entrada en la UI |
|---|---|---|---|
| `/faceswap` | `PrivateRoute` → `AppLayout` | `pages/faceswap/faceswap-page.tsx` | `NAV_ITEMS` de `layouts/app-layout.tsx`, justo después de "Separar pistas": `{ to: '/faceswap', label: 'Cambiar caras', icon: <ScanFace size={18} strokeWidth={2} aria-hidden="true" /> }` (agregar `ScanFace` al import de `lucide-react`) |
| `/admin/plantillas` | `AdminRoute` → `AdminLayout` | `pages/admin/faceswap-templates-page.tsx` | `ADMIN_NAV` de `layouts/admin-layout.tsx`, después de "Planes": `{ to: '/admin/plantillas', label: 'Plantillas de video', icon: <Clapperboard size={17} aria-hidden="true" /> }` (importar de `lucide-react`) |

Las dos páginas van con `lazy()` + `withSuspense()` en `src/router/index.tsx`. El resultado se ve
dentro de `/faceswap` (sin ruta de detalle), así que no hace falta "← Volver". Contextual: el
estado "sin créditos" lleva a `/payments`.

### 7.2 Archivos (convención del repo, cohesionados por la carpeta `faceswap`)

```text
gm_frontend/src/
├── api/
│   ├── endpoints.ts                          # + bloque faceswap
│   └── modules/faceswap.api.ts               # usuario + admin + getFaceSwapErrorMessage
├── types/faceswap.types.ts                   # tipos (estructura_frontend.md: tipos en src/types)
├── hooks/useFaceSwapJob.ts                   # polling (copia de useStemJob)
├── pages/
│   ├── faceswap/faceswap-page.tsx            # orquesta la vista de usuario
│   └── admin/faceswap-templates-page.tsx     # orquesta la vista admin
└── components/faceswap/
    ├── photo-picker.tsx
    ├── source-tabs.tsx
    ├── template-grid.tsx
    ├── template-card.tsx
    ├── clip-uploader.tsx
    ├── consent-check.tsx
    ├── faceswap-submit-bar.tsx
    ├── faceswap-progress.tsx
    ├── faceswap-result.tsx
    ├── faceswap-history.tsx
    ├── faceswap-history-row.tsx
    ├── faceswap-empty-state.tsx
    └── admin/
        ├── template-form.tsx
        ├── template-table.tsx
        └── template-row.tsx
```

`endpoints.ts`:

```ts
faceswap: {
  templates: '/faceswap/templates/',
  jobs: '/faceswap/jobs/',
  job: (id: string) => `/faceswap/jobs/${id}/`,
  resultUrl: (id: string) => `/faceswap/jobs/${id}/result-url/`,
  adminTemplates: '/faceswap/admin/templates/',
  adminTemplate: (id: string) => `/faceswap/admin/templates/${id}/`,
},
```

### 7.3 Tipos TS (`src/types/faceswap.types.ts`) — sin `any`

```ts
export type FaceSwapStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type FaceSwapSourceType = 'template' | 'upload'
export type FaceSwapSourceMode = 'catalog' | 'own'      // pestaña de la UI

export interface FaceSwapTemplate {
  id: string
  title: string
  duration_seconds: number
  has_reference: boolean
  thumbnail_url: string
  preview_url: string
}

export interface AdminFaceSwapTemplate extends FaceSwapTemplate {
  ref_time_s: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface FaceSwapJob {
  id: string
  source_type: FaceSwapSourceType
  template: { id: string; title: string } | null
  source_video_filename: string
  source_duration_seconds: number | null
  model_used: string
  remote_job_id: string | null
  status: FaceSwapStatus
  progress_pct: number
  credits_used: number
  error_message: string | null
  has_result: boolean
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface CreateFaceSwapJobInput {
  photo: File
  consent: boolean
  templateId?: string
  video?: File
}

export interface FaceSwapJobCreated { job_id: string; status: FaceSwapStatus }

export interface TemplateFormValues {
  title: string
  refTimeS: number | null
  isActive: boolean
  video?: File          // solo al crear
  thumbnail?: File
}

export const FACESWAP_CREDIT_COST = 3
export const FACESWAP_MAX_SECONDS = 15
export const FACESWAP_MAX_PHOTO_MB = 8
export const FACESWAP_MAX_VIDEO_MB = 50
```

### 7.4 `faceswap.api.ts`

`getFaceSwapTemplates()`, `createFaceSwapJob(input)` (FormData; `consent` = `'true'`),
`getFaceSwapJobs()`, `getFaceSwapJob(id)`, `deleteFaceSwapJob(id)`,
`getFaceSwapResultUrl(id, download = false)`, `getAdminTemplates()`, `createAdminTemplate(values)`,
`updateAdminTemplate(id, values)` (PATCH multipart), `deleteAdminTemplate(id)`,
`getFaceSwapErrorMessage(error)` (copia de `getStemErrorMessage`) y
`isNoCreditsError(error): boolean` (`isAxiosError && status === 402`). Solo usa `client` y `ENDPOINTS`.

### 7.5 Hook `useFaceSwapJob(jobId: string | null)`

Copia de `useStemJob`: polling cada 4 s (6 s tras error de red) hasta `completed`/`failed`;
devuelve `{ job, status, progress, error, loadingStatus }`. Cuando pasa a `completed`, llama a
`authService.getProfile()` (ya existe en `src/api/auth-service.ts`) y `useAuthStore.setUser(...)`
para refrescar `credit_balance` del sidebar.

### 7.6 Componentes (cada archivo < 120 líneas, una responsabilidad)

| Componente | Responsabilidad | Props clave |
|---|---|---|
| `faceswap-page.tsx` | Estado de la vista (foto, modo, plantilla elegida, clip, consentimiento, `activeJobId`), `useQuery(['faceswap-templates'])` y `useQuery(['faceswap-jobs'])`, recupera el último job activo al entrar (como stems), invalida queries al cambiar de estado. Layout: encabezado (h1 "Cambiar caras" + subtítulo), columna izquierda formulario (pasos 1-2-3), columna derecha progreso/resultado, abajo historial. | — |
| `photo-picker.tsx` | Paso 1: zona de arrastre/clic, preview circular con `URL.createObjectURL` (revocar en cleanup), valida extensión y ≤ 8 MB, botón ghost "Cambiar foto". | `file`, `onChange(file \| null)`, `disabled` |
| `source-tabs.tsx` | Paso 2: pestañas "Catálogo" / "Mi clip" (`role="tablist"`), renderiza `TemplateGrid` o `ClipUploader`. | `mode`, `onModeChange`, `children` |
| `template-grid.tsx` | Grilla responsive de `TemplateCard`; estados cargando (6 skeletons), error con "Reintentar", vacío ("Aún no hay plantillas. Sube tu propio clip." + botón que cambia a "Mi clip"). | `templates`, `isLoading`, `isError`, `selectedId`, `onSelect`, `onRetry`, `onUseOwnClip` |
| `template-card.tsx` | Miniatura 9:16/16:9 con `object-cover`, título, badge de duración `0:08`; al hover reproduce `preview_url` en `<video muted loop playsInline>`; borde `--color-primary` si está seleccionada; `aria-pressed`. | `template`, `selected`, `onSelect` |
| `clip-uploader.tsx` | Selector de video (mp4/mov/webm ≤ 50 MB); lee duración con `<video preload="metadata">` y rechaza > 15 s antes de enviar; muestra nombre, duración y preview. Aviso: "Se reemplaza la cara más grande del video." | `file`, `onChange`, `disabled` |
| `consent-check.tsx` | Checkbox obligatorio: "Confirmo que la foto es mía o tengo permiso de la persona." | `checked`, `onChange`, `disabled` |
| `faceswap-submit-bar.tsx` | Paso 3: costo "3 créditos" + saldo actual (`useAuthStore`), **único botón primario** "Generar video" (deshabilitado + spinner `LoaderCircle` mientras sube o procesa, o si falta foto/fuente/consentimiento). Si saldo < 3 o el POST devolvió 402: mensaje "No tienes créditos suficientes" + botón outline "Recargar créditos" → `navigate('/payments')`. Muestra el error de subida. | `canSubmit`, `submitting`, `noCredits`, `error`, `onSubmit` |
| `faceswap-progress.tsx` | Barra de progreso (`progress_pct`) con textos por tramo: `queued` "En cola…", < 10 "Preparando video…", 10-90 "Cambiando caras…", ≥ 90 "Finalizando…"; nota "Suele tardar entre 2 y 6 minutos. Puedes salir de la página, te avisaremos."; estado `failed` en rojo con `error_message` y "Los créditos no se cobraron." | `status`, `progress`, `error`, `loadingStatus` |
| `faceswap-result.tsx` | Pide `getFaceSwapResultUrl(id)` y muestra `<video controls playsInline>`; si el `<video>` da `onError` (URL vencida) vuelve a pedir la URL una vez; botón outline "Descargar" (`download=1`, abre la URL). | `jobId` |
| `faceswap-history.tsx` | Título "Mis videos" + lista de `FaceSwapHistoryRow`; vacío → `FaceSwapEmptyState`. | `jobs`, `activeJobId`, `onSelect`, `onDelete` |
| `faceswap-history-row.tsx` | Fila: miniatura de la plantilla o icono de video, nombre, fecha, badge de estado con opacidades semánticas (en cola/procesando ámbar, completado verde, error rojo, usando los tokens `--color-warning/success/error`), `· NN%` si activo; botón ghost con icono `Trash2` (deshabilitado si activo, `confirm()` antes de borrar). | `job`, `selected`, `onSelect`, `onDelete` |
| `faceswap-empty-state.tsx` | Icono `ScanFace`, "Aún no has creado videos", "Sube tu foto, elige una plantilla y genera tu primer video." | — |
| `faceswap-templates-page.tsx` (admin) | `useQuery(['admin-faceswap-templates'])`; KPIs mínimos arriba (total, activas); `TemplateForm` (crear/editar) + `TemplateTable`; maneja `editing`. | — |
| `admin/template-form.tsx` | Formulario: título, video (solo al crear), miniatura opcional, "segundo de referencia" (number, step 0.1, vacío = cara más grande) con ayuda contextual, toggle activa. Botón primario "Guardar plantilla" con spinner; "Cancelar" ghost al editar. Muestra errores 400. | `initial`, `onSubmit`, `onCancel`, `submitting`, `error` |
| `admin/template-table.tsx` | Tabla con encabezado `text-xs uppercase tracking-wider`, estados cargando/error/vacío ("No hay plantillas. Crea la primera con el formulario."). | `templates`, `isLoading`, `onEdit`, `onToggle`, `onDelete` |
| `admin/template-row.tsx` | Miniatura, título, duración, ref (`2.5 s` o "Cara más grande"), badge Activa/Inactiva, acciones ghost: Editar, Activar/Desactivar (PATCH `is_active`), Eliminar (`confirm()`). | `template`, `onEdit`, `onToggle`, `onDelete` |

### 7.7 Estados de UI (matriz)

| Estado | Dónde | Qué ve el usuario |
|---|---|---|
| Vacío | historial, catálogo | empty states accionables (7.6) |
| Cargando | catálogo, historial, estado del job | skeletons / "Cargando…" con `--text-subdued` |
| Subiendo | submit bar | botón deshabilitado + spinner "Subiendo…" |
| Procesando | panel derecho | `FaceSwapProgress` con % real de Modal; formulario deshabilitado |
| Completado | panel derecho | `FaceSwapResult` + toast/notificación existente (`faceswap_ready`) |
| Error | panel derecho / submit bar | mensaje del backend; "Los créditos no se cobraron." si `failed` |
| Sin créditos | submit bar | aviso + "Recargar créditos" → `/payments`; botón primario deshabilitado |

Estilo: tokens de `docs/ui-specification.md` (cards `--bg-card` → `--bg-card-hover`, radio 8 px,
botón primario píldora `--color-primary`), tipografía h1 32 px/700. Sin hex sueltos.

---

## 8. Tests (Modal y R2 siempre mockeados)

### 8.1 `gm_backend/apps/faceswap/tests.py` (`django.test.TestCase`, estilo `apps/stems/tests.py`)

**`PhotoValidationTests`** (imágenes generadas con Pillow en memoria + `SimpleUploadedFile`)
- acepta JPG, PNG y WEBP y deja `seek(0)`.
- rechaza `.gif`, archivo vacío, bytes corruptos con `.jpg`, > `FACESWAP_MAX_PHOTO_BYTES`
  (`@override_settings` con un tope chico) y 64×64 px.

**`VideoValidationTests`** (`@patch('apps.faceswap.services.media_validation.subprocess.run')`)
- acepta MP4 de 10 s; rechaza `.avi`; rechaza 16 s; acepta 15,4 s (tolerancia); rechaza salida
  sin `streams`; rechaza `CalledProcessError`; rechaza > `FACESWAP_MAX_VIDEO_BYTES`.

**`FaceSwapRequestTests`** (`@patch` de `validate_photo`, `validate_video`, `upload_fileobj`,
`process_faceswap_job.delay`)
- crea job `queued`, una `CreditReservation(reserved, amount=3, reference_type='faceswap_job')` y encola.
- 402 sin créditos: no crea job ni reserva.
- 409 con job activo; job activo sin foto y viejo se marca `failed` y deja crear uno nuevo.
- plantilla inactiva o borrada → `TemplateUnavailableError`.
- sin consentimiento / 0 fuentes / 2 fuentes → error antes de validar archivos.
- fallo de R2 al subir → job `failed`, reserva `released`.
- fallo al encolar (Redis) → borra las claves subidas (`delete_file` llamado) y libera.

**`FaceSwapTaskTests`** (`@patch('apps.faceswap.tasks.submit_faceswap_job')`, `get_faceswap_job_status`,
`ml.storage_client.get_storage_client`, `get_storage_bucket`, `poll_faceswap_job.apply_async`)
- submit guarda `remote_job_id` y `started_at` y programa poll; con `remote_job_id` previo no reenvía.
- poll `processing` actualiza `progress_pct` y reprograma.
- poll `completed` valida `head_object`, confirma reserva, `credits_used=3`, `progress=100`,
  borra foto y clip subido (no borra el video de plantilla).
- **idempotencia**: ejecutar el poll `completed` dos veces → un solo `CreditTransaction` y saldo −3.
- objeto R2 vacío o clave fuera de `faceswap/results/` → `failed` + reserva liberada.
- poll `failed` → `failed`, reserva liberada, inputs borrados, saldo intacto.
- timeout (`started_at` viejo) → `failed` sin llamar a Modal.
- reserva `released` → nunca cobra (`ValueError` → `failed`).

**`FaceSwapApiTests`** (`APIClient.force_authenticate`)
- `GET templates/` solo activas y no borradas (`generate_presigned_url` mockeado).
- endpoints admin → 403 para usuario normal; 201/200/204 para admin (`is_staff=True`).
- `POST admin/templates/` con `ref_time_s` > duración → 400.
- `DELETE jobs/{id}/` activo → 409; completado → 204, `deleted_at` seteado y `delete_file(output)` llamado; deja de aparecer en el listado.
- `GET jobs/{id}/result-url/` → 409 si no está listo; 200 con `?download=1` pasa `attachment`.
- job de otro usuario → 404 en detalle, borrar y result-url.

**`FaceSwapRecoveryTests`** (o en `apps/core/tests_recovery.py`, siguiendo su estilo)
- job `processing` viejo con reserva válida → `recover_faceswap_job.delay` llamado.
- job viejo con reserva vencida → `failed`, reserva `released`, contador `failed` +1.

### 8.2 `gm_backend/ml/test_modal_faceswap.py` (`unittest.TestCase`, `FakeDict` como en `test_modal_demucs.py`)
- `_claim_job('client-1')` dos veces → mismo id.
- fallo de spawn queda `retryable` sin segundo spawn concurrente (como Demucs).
- `_facefusion_command(..., ref_time_s=2.5)` contiene `reference`, `--reference-frame-number 62`,
  `inswapper_128_fp16`, `codeformer`, `45`, `256x256`; con `None` contiene `one` y `large-small`.
- mapeo de progreso: FaceFusion 0/50/100 → 10/50/90.
- `_validate_key` rechaza `''`, `/abs` y `a/../b`.

### 8.3 `gm_backend/ml/test_modal_contract.py` (agregar)
- `modal_faceswap_server.py` contiene `requires_proxy_auth=True`, `from .modal_app import app`,
  `action") == "status"`, `client_job_id`, `output_s3_key`, `music-gen-secret`, `FACESWAP_SPAWN_LEASE_SECONDS`.
- **no** contiene `drawtext` ni `faceswap-data`.
- `modal_music_server.py` importa `modal_faceswap_server` y **no** instala `facefusion`/`onnxruntime`.

### 8.4 `gm_backend/ml/test_modal_client.py` (agregar)
- `submit_faceswap_job` agrega `async: true`, reintenta timeout con el mismo `client_job_id`.
- `get_faceswap_job_status` lanza `ModalGenerationError` si falta `progress_pct`.

Ejecución (dentro del contenedor ya levantado, **sin reiniciarlo**):
`docker exec musical_backend_dev python manage.py test apps.faceswap ml.test_modal_faceswap ml.test_modal_contract ml.test_modal_client`.
Frontend: `npm run build` (incluye `tsc -b`) y `npm run lint`.

---

## 9. Documentación a actualizar (sin ejecutar nada)

1. **`gm_backend/docs/01_API_CONTRACT.md`**: nueva sección `## Cambiar caras (Face Swap)` después de
   `## Stems`, con el bloque de rutas de §3.1 (marcando `[admin]`) y un párrafo: valida JPG/PNG/WEBP
   ≤ 8 MB y MP4/MOV/WEBM ≤ 50 MB y ≤ 15 s; cuesta 3 créditos (reserva al crear, cobra al completar,
   libera si falla); un job activo por usuario (409); las fotos y clips propios se borran al terminar.
2. **`.env.example`** (raíz): variables de §5.4 en la sección 8.
3. **`Guia_Crear_Modal.md`**: nueva sección **"10. Face Swap (FaceFusion)"**:
   - se despliega con el **mismo** comando `modal deploy ml/modal_music_server.py` (que importa
     `modal_faceswap_server.py`); **no** desplegar `modal_faceswap_server.py` por separado;
   - la primera vez construye una imagen CUDA (≈ 10 min) y FaceFusion descarga los modelos al
     Volume `gm-faceswap-models` en el primer job (más lento);
   - copiar la URL de la función `face_swap` en `MODAL_ENDPOINT_FACESWAP`;
   - recursos: Dict `gm-faceswap-job-status`, Volume `gm-faceswap-models`, GPU T4 (`FACESWAP_GPU`);
   - tiempos de referencia: ~2,5 min (plantilla 8 s, 720p) a ~5,5 min (clip 12 s);
   - problemas frecuentes: "Failed to initialize CUDNN Frontend" (parche T4), "No se detectó una cara".
   - Actualizar la tabla del §8 ("cuatro URLs" → "cinco URLs") con `MODAL_ENDPOINT_FACESWAP | face_swap`.
4. **`README.md`** (opcional, una línea cada uno): tabla 1.1 fila Modal "+ FaceFusion" y
   lista 1.2 "Cambio de caras en videos cortos".

---

## 10. Riesgos y límites conocidos

1. **Sin R2 ni Modal en local**: subida, procesamiento y URLs firmadas no se pueden probar de punta
   a punta en este entorno; todo se cubre con mocks. La prueba real requiere desplegar en Modal
   (lo hace el usuario, no los agentes) y configurar `MODAL_ENDPOINT_FACESWAP`.
2. **Riesgo de deploy**: desplegar `ml/modal_faceswap_server.py` directamente reemplazaría la app
   `gm-music-server` sin las funciones de música y Demucs. Siempre desplegar `modal_music_server.py`.
3. **Recuperación sin Beat**: `recover_abandoned_operations` no está agendada en Beat (preexistente).
   Si un worker de Celery muere a mitad de un poll, el job queda `processing` hasta que alguien la
   ejecute; la reserva vence a la hora (no cobra), pero el job bloquea al usuario (1 activo) hasta
   entonces. Mitigación incluida: el chequeo de job abandonado al crear (§4.4) solo cubre subidas
   abandonadas. Decisión del equipo: agendar la tarea en Beat.
4. **Celery debe recargar**: las tareas nuevas (`apps.faceswap.tasks.*`) solo existen en el worker
   tras reiniciarlo. Los agentes no reinician contenedores; avisar al usuario.
5. **Migraciones**: `makemigrations faceswap notifications` + `migrate` en el contenedor del backend.
6. **Costo y tiempo GPU**: 2-6 min de T4 por job; `max_containers=2` limita la cola global (otros
   usuarios esperan en `queued`). Arranque en frío extra la primera vez (imagen + modelos).
7. **Uso indebido / deepfakes**: solo hay consentimiento declarativo, no verificación de identidad.
   No hay marca de agua (requisito), así que el resultado no se distingue como IA. Considerar
   términos de uso.
8. **Licencia de modelos**: `inswapper_128` tiene licencia **no comercial**; válido para el proyecto
   académico, no para producción comercial.
9. **Selección de cara**: en clips propios se cambia solo la cara más grande por frame; con varias
   personas de tamaño similar puede saltar entre caras. En plantillas, `ref_time_s` mal elegido
   (frame sin cara o con varias) hace que falle o cambie la cara equivocada.
10. **URLs firmadas de 1 h**: el `<video>` puede quedar con URL vencida si la pestaña queda abierta;
    `FaceSwapResult` re-pide la URL una vez ante `onError`.
11. **Retención**: los resultados quedan en R2 hasta que el usuario borra el job (no hay expiración
    automática; fuera de alcance).
12. **Duplicación de código Modal**: los helpers de claim/lease se copian de Demucs (no se
    refactoriza código del equipo). Un fix futuro en uno debe replicarse en el otro.

---

## 11. Lista exacta de archivos

### Backend (Django)
Crear:
- `gm_backend/apps/faceswap/__init__.py`
- `gm_backend/apps/faceswap/apps.py` (`FaceswapConfig`, `name='apps.faceswap'`)
- `gm_backend/apps/faceswap/admin.py` (registro simple de ambos modelos)
- `gm_backend/apps/faceswap/models.py`
- `gm_backend/apps/faceswap/serializers.py`
- `gm_backend/apps/faceswap/views.py`
- `gm_backend/apps/faceswap/urls.py`
- `gm_backend/apps/faceswap/tasks.py`
- `gm_backend/apps/faceswap/services/__init__.py`
- `gm_backend/apps/faceswap/services/faceswap_service.py`
- `gm_backend/apps/faceswap/services/media_validation.py`
- `gm_backend/apps/faceswap/services/template_service.py`
- `gm_backend/apps/faceswap/migrations/__init__.py`
- `gm_backend/apps/faceswap/migrations/0001_initial.py` (generada)
- `gm_backend/apps/faceswap/tests.py`
- `gm_backend/apps/notifications/migrations/0002_alter_notification_type.py` (generada; nombre real el que dé `makemigrations`)

Modificar:
- `gm_backend/config/settings.py` (INSTALLED_APPS + variables §5.4)
- `gm_backend/config/urls.py` (`api/faceswap/`)
- `gm_backend/ml/modal_client.py` (2 funciones nuevas)
- `gm_backend/apps/core/tasks.py` (rama `faceswap` en `_remote_state` + bloque de recuperación)
- `gm_backend/apps/notifications/models.py` y `gm_backend/apps/notifications/services.py` (`faceswap_ready`)
- `gm_backend/ml/test_modal_client.py`, `gm_backend/ml/test_modal_contract.py`
- `gm_backend/docs/01_API_CONTRACT.md`
- `.env.example`

### Modal
Crear:
- `gm_backend/ml/modal_faceswap_server.py`
- `gm_backend/ml/test_modal_faceswap.py`

Modificar:
- `gm_backend/ml/modal_music_server.py` (import de `FaceSwapServer, face_swap` en ambas ramas)
- `Guia_Crear_Modal.md` (sección 10 + tabla de URLs)

### Frontend
Crear:
- `gm_frontend/src/types/faceswap.types.ts`
- `gm_frontend/src/api/modules/faceswap.api.ts`
- `gm_frontend/src/hooks/useFaceSwapJob.ts`
- `gm_frontend/src/pages/faceswap/faceswap-page.tsx`
- `gm_frontend/src/pages/admin/faceswap-templates-page.tsx`
- `gm_frontend/src/components/faceswap/photo-picker.tsx`
- `gm_frontend/src/components/faceswap/source-tabs.tsx`
- `gm_frontend/src/components/faceswap/template-grid.tsx`
- `gm_frontend/src/components/faceswap/template-card.tsx`
- `gm_frontend/src/components/faceswap/clip-uploader.tsx`
- `gm_frontend/src/components/faceswap/consent-check.tsx`
- `gm_frontend/src/components/faceswap/faceswap-submit-bar.tsx`
- `gm_frontend/src/components/faceswap/faceswap-progress.tsx`
- `gm_frontend/src/components/faceswap/faceswap-result.tsx`
- `gm_frontend/src/components/faceswap/faceswap-history.tsx`
- `gm_frontend/src/components/faceswap/faceswap-history-row.tsx`
- `gm_frontend/src/components/faceswap/faceswap-empty-state.tsx`
- `gm_frontend/src/components/faceswap/admin/template-form.tsx`
- `gm_frontend/src/components/faceswap/admin/template-table.tsx`
- `gm_frontend/src/components/faceswap/admin/template-row.tsx`

Modificar:
- `gm_frontend/src/api/endpoints.ts`
- `gm_frontend/src/router/index.tsx`
- `gm_frontend/src/layouts/app-layout.tsx` (`NAV_ITEMS` + import `ScanFace`)
- `gm_frontend/src/layouts/admin-layout.tsx` (`ADMIN_NAV` + import `Clapperboard`)

### Fuera de alcance (no tocar)
- `/home/lmc/projects/faceswap/**` (solo lectura).
- `ml/modal_demucs_server.py`, `apps/stems/**`, `apps/credits/**` (se reutilizan, no se editan).
- `workers/celery.py` (no se agenda Beat; ver §10.3).
- `~/.modal.toml`, credenciales, comandos `modal`, contenedores.

---

## 11. Extensión: elegir el personaje (clic sobre la cara)

**Objetivo:** el usuario elige A QUIÉN se le cambia la cara. Pausa el video base en un momento donde se vea el personaje y hace clic sobre su cara. Solo esa persona se reemplaza en todo el video, siguiendo su identidad con el modo `reference` de FaceFusion. Es opcional: si no hace clic, se mantiene el comportamiento actual (referencia de la plantilla o la cara más grande).

### 11.1 Contrato API (cambio compatible)
`POST /api/faceswap/jobs/` (multipart) acepta 3 campos opcionales nuevos, **todos o ninguno**:
- `ref_time_s`: segundo del video base (float ≥ 0 y ≤ duración del video base). Si se envía, reemplaza al `ref_time_s` de la plantilla.
- `face_x`, `face_y`: posición del clic normalizada al **fotograma real del video** (0..1; 0,0 = esquina superior izquierda), NO al elemento `<video>` con bandas negras.

Errores 400 (formato `{"error": ...}`):
- `"Para elegir el personaje envía ref_time_s, face_x y face_y juntos."`
- `"La posición de la cara debe estar entre 0 y 1."`
- `"El momento elegido está fuera del video."`

`FaceSwapJob` suma `target_face_x` y `target_face_y` (FloatField, null). `ref_time_s` ya existe. El serializer de detalle y de lista expone `ref_time_s`, `target_face_x` y `target_face_y`.

### 11.2 Contrato Modal
El body de submit suma `face_x` y `face_y` (float o null). Con `face_x` y `face_y` + `ref_time_s`, el worker:
1. Normaliza el video igual que hoy. Las coordenadas se mapean al video normalizado: si la normalización recorta, rellena o rota, hay que transformarlas.
2. Detecta las caras en el fotograma `round(ref_time_s * TARGET_FPS)` del video normalizado, **con el mismo detector y el mismo orden que usa FaceFusion**, para que el índice coincida.
3. Elige la cara cuyo bbox contiene el clic. Si ninguna lo contiene, la de centro más cercano, con una distancia máxima razonable.
4. Pasa `--face-selector-mode reference --reference-frame-number N --face-selector-order large-small --reference-face-position <índice de esa cara en orden large-small>`.
5. Si no hay ninguna cara cerca del clic, falla con `"No se encontró una cara en el punto elegido. Elige otro momento del video."` (el backend libera la reserva como en cualquier fallo).

Sin `face_x` y `face_y`: el comportamiento es el actual.

### 11.3 Frontend
Un componente nuevo `face-target-picker` aparece cuando ya hay video base (plantilla o clip propio):
- Un `<video>` con controles propios para buscar el momento (barra de tiempo) y pausar.
- Al hacer clic en el fotograma pausado, se calcula `face_x` y `face_y` sobre el **área real del video**, descontando el letterbox de `object-fit: contain`, y se marca un círculo.
- Texto de ayuda: "Pausa donde se vea bien la cara y haz clic sobre ella. Si no eliges, se cambiará la cara principal."
- Acción secundaria "Quitar selección".
- Si se cambia la plantilla o el clip, la selección se limpia.
- Se envían los 3 campos solo si hay selección.

**Ajustes de QA (11.1):** el backend acepta `ref_time_s` hasta 0.05 s después del final (redondeo entre el navegador y ffprobe) y guarda `min(ref_time_s, duración, FACESWAP_MAX_SECONDS)`, para no chocar con el límite de 15 s de Modal. Verificado con GPU real el 2026-11-19: un clic sobre la cara eligió el personaje (fotograma 75, posición 0); un clic sin cara falló con el mensaje de la spec y la reserva quedó `released`.
