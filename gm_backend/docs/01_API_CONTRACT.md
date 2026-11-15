# MusicAI — Contrato de la API

Base URL local: `http://localhost:8000`. Salvo el webhook de Stripe, los endpoints requieren:

```http
Authorization: Bearer <access-token>
```

Los identificadores de recursos son UUID cuando la ruta usa `<uuid:...>`. Los errores de validación usan normalmente `400`; saldo insuficiente usa `402`; recursos no autorizados o inexistentes usan `403` o `404`.

## Autenticación

```text
POST /api/auth/register/          {email, password, full_name} → usuario + tokens
POST /api/auth/login/             {email, password} → access, refresh
POST /api/auth/refresh/           {refresh} → access
GET  /api/auth/me/                → perfil del usuario autenticado
POST /api/auth/logout/            {refresh} → 204
POST /api/auth/change-password/   {old_password, new_password} → 200
GET  /api/auth/fcm-token/         → token FCM guardado
POST /api/auth/fcm-token/         {fcm_token} → 200
POST /api/auth/firebase-token/    → {firebase_token}
```

## Canciones

```text
POST  /api/songs/generate/           → {job_id, song_id, status}
POST  /api/songs/upload/             multipart: file, title? → canción subida lista
GET   /api/songs/jobs/{id}/          → estado de GenerationJob
GET   /api/songs/library/            → canciones generadas del usuario
GET   /api/songs/library/?context=karaoke → canciones propias listas para Karaoke
GET   /api/songs/tags/               → tags disponibles
GET   /api/songs/{id}/               → detalle de canción
PATCH /api/songs/{id}/               {title?, is_public?}
DELETE /api/songs/{id}/              → 204; soft delete
GET   /api/songs/{id}/play-url/      → {url} prefirmada temporal
GET   /api/songs/{id}/thumbnail-url/ → {url} prefirmada temporal
POST  /api/songs/{id}/like/          → estado del like
```

Las canciones subidas se registran con `source_type=uploaded`, quedan privadas y no pueden publicarse en la comunidad. La subida no crea un `GenerationJob` ni consume créditos.

## Stems

```text
POST /api/stems/separate/                 multipart: file → {job_id} (201)
GET  /api/stems/jobs/                     → trabajos del usuario
GET  /api/stems/jobs/{id}/                → estado, progreso y stems
GET  /api/stems/files/{id}/download-url/  → {url}; ?download=1 fuerza descarga
```

La separación valida MP3/WAV, contenido decodificable, tamaño y duración. Consume créditos al completar correctamente.

## Karaoke

```text
GET  /api/karaoke/catalog/                    → canciones listas disponibles
POST /api/karaoke/songs/{song_id}/generate/   → crea o adquiere Karaoke
GET  /api/karaoke/{id}/status/                → estado del procesamiento
GET  /api/karaoke/{id}/play/                  → URLs prefirmadas y timestamps
GET  /api/karaoke/my-library/                 → karaokes adquiridos
POST /api/karaoke/rooms/                      {karaoke_id} → sala creada
POST /api/karaoke/rooms/{room_code}/join/     → acceso a sala
```

Crear Karaoke cuesta 2 créditos. El estado puede ser `queued`, `processing`, `ready` o `failed`. La reproducción requiere acceso pagado; el estado solo se muestra a usuarios autorizados.

## Mix DJ

```text
GET   /api/mix/projects/                                  → proyectos propios
POST  /api/mix/projects/                                  {title?, description?, bpm?}
GET   /api/mix/projects/{mix_id}/                         → detalle
PATCH /api/mix/projects/{mix_id}/                         → edición del proyecto
DELETE /api/mix/projects/{mix_id}/                        → soft delete
POST  /api/mix/projects/{mix_id}/clips/                   → crea clip
PATCH /api/mix/projects/{mix_id}/clips/{clip_id}/         → edita clip
DELETE /api/mix/projects/{mix_id}/clips/{clip_id}/        → elimina clip
POST  /api/mix/projects/{mix_id}/clips/{clip_id}/split/   {playhead_ms}
POST  /api/mix/projects/{mix_id}/reorder/                 {clip_ids}
POST  /api/mix/projects/{mix_id}/export/                  {format, quality, muted_clip_ids?, solo_clip_ids?}
GET   /api/mix/exports/{export_id}/                       → estado y URL de descarga
```

Los formatos son `mp3` y `wav`. `wav` requiere `quality=lossless`; `lossless` no es válido para MP3. Una exportación cuesta 3 créditos.

## Créditos y pagos

```text
GET    /api/credits/balance/
GET    /api/credits/plans/
POST   /api/credits/plans/                         [admin]
PUT    /api/credits/plans/{id}/                    [admin]
DELETE /api/credits/plans/{id}/                    [admin]
POST   /api/credits/checkout/                      {plan_slug}
POST   /api/credits/pay/                           {payment_method_id, amount, plan_slug?}
GET    /api/credits/pay/                           → pagos del usuario
GET    /api/credits/transactions/
GET    /api/credits/subscriptions/
GET    /api/credits/payment-methods/
POST   /api/credits/payment-methods/               {payment_method_id}
DELETE /api/credits/payment-methods/{id}/
POST   /api/credits/stripe-webhook/                [sin JWT; Stripe]
GET    /api/credits/stripe/prices/                 [admin]
POST   /api/credits/stripe/prices/                 [admin]
DELETE /api/credits/stripe/prices/{price_id}/      [admin]
```

## Comunidad

```text
GET  /api/community/feed/
GET  /api/community/trending/
GET  /api/community/stats/
POST /api/community/songs/{song_id}/like/
POST /api/community/songs/{song_id}/play/          {seconds_played?, source?}
```

Solo las canciones públicas aparecen en el feed y las consultas de comunidad.

## Playlists, recomendaciones y notificaciones

```text
GET    /api/playlists/
POST   /api/playlists/
GET    /api/playlists/{id}/
PATCH  /api/playlists/{id}/
DELETE /api/playlists/{id}/
POST   /api/playlists/{id}/songs/                  {song_id}
DELETE /api/playlists/{id}/songs/{song_id}/
POST   /api/playlists/{id}/share/
GET    /api/playlists/public/{token}/
GET    /api/playlists/auto/
POST   /api/playlists/auto/generate/

GET  /api/recommendations/for-you/
GET  /api/recommendations/suggested-tags/

GET   /api/notifications/
PATCH /api/notifications/{notif_id}/read/
POST  /api/notifications/read-all/
```

## Reportes y documentación

```text
GET /api/reports/usage/       [admin]
GET /api/reports/top-songs/   [admin]
GET /api/reports/audit-logs/  [admin]
GET /api/reports/users/       [admin]
GET /api/schema/              esquema OpenAPI
GET /api/docs/                interfaz Swagger UI
```

Los contratos se implementan en `apps/<dominio>/urls.py` y sus views/serializers correspondientes. Cualquier cambio de ruta, método, body o respuesta debe actualizar este documento y sus consumidores.
