# `gm_backend` — Arquitectura Django Modular + Service Layer

Backend Django 5 + Django REST Framework + Celery + PostgreSQL 16 + Cloudflare R2 + Modal.

---

## Estructura General

```text
gm_backend/
├── config/                 # settings.py, urls.py (enrutamiento /api/<modulo>/)
├── workers/                # celery.py (colas + beat_schedule: playlists diarias + rescate cada 10 min)
├── ml/                     # Clientes R2 (storage_client.py), Modal (modal_client.py) y servidores GPU
└── apps/
    └── <modulo>/           # Convención uniforme por dominio
        ├── models.py       # Entidades y estados del dominio
        ├── serializers.py  # Contratos DTO de entrada y salida
        ├── views.py / views/  # Vistas delgadas (validar → delegar a service → responder)
        ├── urls.py         # Rutas del módulo
        ├── services/       # Lógica de negocio, transacciones y reservas de créditos
        ├── tasks.py        # Tareas asíncronas Celery y polling a Modal/workers
        └── tests.py        # Tests unitarios y de contrato
```

---

## Catálogo de Apps (`apps/`)

| App | Responsabilidad | Archivos clave |
|---|---|---|
| `core` | BaseModel, permisos (`IsAdmin`), recuperación de jobs abandonados | `services/recovery_service.py`, `services/recovery_domains.py`, `tasks.py` |
| `users` | Registro, login JWT, perfil, cambio de password, roles | `models.py`, `services.py`, `views.py` |
| `credits` | Saldo, planes, reservas idempotentes, pagos/tarjetas Stripe | `services/credit_service.py`, `services/stripe_service.py`, `serializers.py` |
| `songs` | Generación IA, subida propia, biblioteca, tags, listado de jobs | `services/generation_service.py`, `services/song_upload_service.py`, `views.py` |
| `humming` | Tarareo CPU (`gm_tarareo`) + mejora IA (`CoverServer`) | `services/job_service.py`, `services/result_service.py`, `services/choice_service.py` |
| `stems` | Separación vocal/instrumental desde archivo o desde `Song` (`song_id`) | `services/stem_service.py`, `tasks.py`, `views.py` |
| `translations` | Doblaje de videos musicales con Modal | `services/translation_service.py`, `tasks.py` |
| `faceswap` | Plantillas admin + intercambio de rostro en video | `services/faceswap_service.py`, `services/template_service.py`, `tasks.py` |
| `karaoke` | Generación de pista karaoke + timestamps de letra + salas | `services/`, `tasks.py`, `views.py` |
| `mix` | Proyectos DJ multipista, clips, splits, exportación `ffmpeg` | `views/project_views.py`, `views/clip_views.py`, `views/export_views.py`, `services/` |
| `playlists` | Playlists manuales, públicas compartidas y automáticas | `services/auto_playlist_service.py`, `views.py` |
| `community` | Feed público, trending 48h, likes y conteo de reproducciones | `services.py`, `views.py` |
| `recommendations` | Recomendaciones "Para ti" y tags sugeridos | `services/`, `views.py` |
| `reports` | Dashboard admin real (`GET /api/reports/dashboard/`), gestión usuarios (`PATCH`), top canciones, auditoría | `services/dashboard_service.py`, `services/users_admin_service.py`, `views.py` |
| `assistant` | Chat de onboarding (`POST /api/assistant/chat/`): guía estática cacheada + contexto del usuario, salida JSON con acciones filtradas; no cobra créditos, 30/h | `services/knowledge.py`, `services/context.py`, `services/llm_client.py`, `views.py` |
| `notifications` | Notificaciones in-app + envío push FCM | `services.py`, `firebase.py` |
| `audit` | Registro de auditoría (`AuditLog` y `log_action`) | `models.py`, `services.py` |

---

## Reglas de Mantenimiento
1. **Vistas delgadas:** nunca poner lógica compleja de negocio ni transacciones `select_for_update` dentro de `views.py`; delegar a `services/`.
2. **Créditos seguros:** toda función IA reserva créditos (`reserve_credits`) y los confirma al completar o los libera en fallo/timeout (`recover_abandoned_operations`).
3. **No romper `ml/modal_*.py`:** cualquier módulo nuevo importado por Modal requiere incluirse en `add_local_python_source` de las imágenes en `ml/modal_music_server.py`.
