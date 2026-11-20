# MusicAI (`musical-system`) — Mapa Maestro del Proyecto

Monorepo de MusicAI: backend Django 5 + DRF + Celery/Redis (`gm_backend/`), frontend React 19 + Vite + Tailwind (`gm_frontend/`), worker CPU de tarareo (`gm_tarareo/`) e inferencia GPU en Modal + almacenamiento R2.

---

## Patrón de Diseño Simétrico (Back ↔ Front)

La arquitectura sigue **1 funcionalidad = 1 módulo con el mismo dominio en Backend y Frontend**:

- **Backend (`gm_backend/apps/<modulo>/`):** *Django Modular App + Service Layer* (`models.py`, `serializers.py`, `views.py` o `views/`, `urls.py`, `services/`, `tasks.py`, `tests.py`).
- **Frontend (`gm_frontend/src/features/<modulo>/`):** *Base UI Kit + Feature-Based Mirror* (`api/`, `components/`, `hooks/`, `pages/`, `types/`, `lib/`).

Para buscar o modificar cualquier funcionalidad, ubica su módulo en la tabla inferior:

---

## Mapa Funcionalidad → Frontend → Backend → Workers

| Funcionalidad | Ruta Front | Feature Front (`gm_frontend/src/features/`) | App Back (`gm_backend/apps/`) | Prefijo API | Worker / GPU |
|---|---|---|---|---|---|
| Landing e Inicio | `/`, `/inicio` | `home/` | `community/`, `recommendations/` | `/api/community/`, `/api/recommendations/` | — |
| Autenticación | `/login`, `/register` | `auth/` | `users/` | `/api/auth/` | — |
| Crear canción y Biblioteca | `/create`, `/library` | `songs/` | `songs/` | `/api/songs/` | Celery → Modal A100 (`MusicGenServer`) |
| Tarareo y mejora IA | `/humming` | `humming/` | `humming/` | `/api/humming/` | `gm_tarareo` (CPU) + Modal A10G (`CoverServer`) |
| Separar pistas (Stems) | `/stems` | `stems/` | `stems/` | `/api/stems/` | Celery → Modal T4 (`DemucsServer`) |
| Doblaje / Traducciones | `/traducciones` | `translations/` | `translations/` | `/api/translations/` | Celery → Modal A10G (`gm-translation-server`) |
| Cambiar caras (Faceswap) | `/faceswap` | `faceswap/` | `faceswap/` | `/api/faceswap/` | Celery → Modal T4 (`FaceSwapServer`) |
| Karaoke y salas | `/karaoke`, `/karaoke/*` | `karaoke/` | `karaoke/` | `/api/karaoke/` | Celery + Demucs/Whisper/Gemini (+ Firebase opt.) |
| Mix DJ multipista | `/mix`, `/mix/:id` | `mix/` | `mix/` | `/api/mix/` | Celery CPU (`ffmpeg`/`pydub`) |
| Playlists y compartidas | `/playlists`, `/playlists/:id`, `/playlists/public/:token` | `playlists/` | `playlists/` | `/api/playlists/` | Celery Beat diario |
| Comunidad | `/community` | `community/` | `community/` | `/api/community/` | — |
| Para ti | `/recommendations` | `recommendations/` | `recommendations/` | `/api/recommendations/` | Tags + `ml/predictor.py` |
| Pagos, Plan y Perfil | `/payments`, `/profile` | `billing/` | `credits/`, `users/` | `/api/credits/`, `/api/auth/` | Stripe |
| Panel Administrador | `/admin`, `/admin/*` | `admin/` | `reports/`, `credits/`, `faceswap/`, `audit/` | `/api/reports/`, `/api/credits/`, `/api/faceswap/admin/` | — |
| Infraestructura transversal | `components/ui/`, `components/layout/`, `store/` | Transversal | `core/`, `notifications/`, `audit/` | `/api/notifications/` | Celery Beat (`recover_abandoned_operations`) |

---

## Reglas Rápidas de Desarrollo
- **Cero código monolítico:** mantener componentes y servicios por debajo de ~200 líneas dividiéndolos en subcomponentes/servicios.
- **Módulos aislados:** un feature en `gm_frontend/src/features/` solo importa de `src/components/ui/`, `src/lib/`, `src/store/` o APIs/componentes explícitos de otro feature (nunca duplicar botones/modales propios fuera de `components/ui/`).
- **Verificación local en Docker:**
  - Backend: `docker exec musical_backend_dev python manage.py check && docker exec musical_backend_dev python manage.py test`
  - Frontend: `docker exec musical_frontend_dev sh -c "npx tsc -b --noEmit && npm run lint && npm run build"`
