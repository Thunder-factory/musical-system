<div align="center">

# MusicAI

### Plataforma web para generación musical, Karaoke colaborativo y producción de audio

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.0-092E20?style=for-the-badge&logo=django&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**Generación musical · Karaoke · Stems · Mix DJ · Playlists · Comunidad**

</div>

## Índice

1. [Descripción](#1-descripción)
2. [Arquitectura](#2-arquitectura)
3. [Tecnologías](#3-tecnologías)
4. [Estructura](#4-estructura-del-proyecto)
5. [Requisitos](#5-requisitos-previos)
6. [Variables](#6-variables-de-entorno)
7. [Instalación](#7-instalación-y-ejecución)
8. [Docker](#8-servicios-docker)
9. [Acceso](#9-acceso-a-la-aplicación)
10. [Desarrollo](#10-entorno-de-desarrollo)
11. [Problemas](#11-solución-de-problemas)

---

# 1. Descripción

MusicAI es una plataforma web para crear canciones mediante inteligencia artificial, preparar Karaoke, separar stems, editar mezclas y organizar una biblioteca musical.

## 1.1 Componentes principales

| Componente | Responsabilidad |
|---|---|
| API Django | Usuarios, JWT, créditos, canciones y reglas de negocio. |
| React/Vite | Generación, reproducción, Karaoke, Mix y administración. |
| Celery/Redis | Trabajos asíncronos y seguimiento de procesos. |
| Modal | ACE-Step, Qwen, SDXL y Demucs. |
| Cloudflare R2 | Audio, portadas, stems y exportaciones privadas. |
| PostgreSQL | Usuarios, metadatos, créditos y estados. |
| Firebase | Salas Karaoke y notificaciones FCM. |

## 1.2 Funcionalidades

- Generación desde descripción, prompt o letra.
- Subida de canciones propias sin generación automática de Karaoke.
- Biblioteca, comunidad, playlists y recomendaciones.
- Separación de voces e instrumental con Whisper.
- Salas Karaoke colaborativas.
- Edición secuencial de clips y exportación Mix DJ.
- Créditos, plan Free, suscripciones y pagos Stripe.

---

# 2. Arquitectura

MusicAI utiliza una arquitectura cliente-servidor con procesamiento asíncrono.

| Capa | Componentes |
|---|---|
| Presentación | React 19, Vite, TypeScript y Firebase Web. |
| Aplicación | Django REST Framework, JWT y servicios de dominio. |
| Trabajos | Celery Worker, Celery Beat y Redis. |
| IA | MusicGenServer para generación y DemucsServer para separación. |
| Datos | PostgreSQL y Cloudflare R2. |

### Generación musical

React solicita una canción, Django crea el trabajo y la reserva de créditos, Celery invoca Modal, los archivos se guardan en R2 y Django finaliza el estado y el cobro de forma idempotente.

### Karaoke y Mix

Karaoke utiliza Demucs y Whisper. Firebase sincroniza las salas. Mix DJ descarga clips de R2, aplica cortes, fades, volumen y Mute/Solo, y almacena la exportación en R2.

---

# 3. Tecnologías

| Área | Tecnologías |
|---|---|
| Backend | Python 3.12, Django 5, DRF, SimpleJWT y PostgreSQL 16. |
| Asíncrono | Celery 5.6 y Redis 7. |
| Audio/IA | Modal, boto3, R2, FFmpeg, Whisper, pydub y Gemini. |
| Frontend | React 19, TypeScript, Vite 8, React Router 7, Zustand y Axios. |
| UI | Tailwind CSS y CSS Modules. |
| Pagos | Stripe y Stripe.js. |
| Infraestructura | Docker Compose y Git. |

---

# 4. Estructura del proyecto

~~~text
musical-system/
├── gm_backend/
│   ├── apps/              # Dominios Django
│   ├── config/            # Settings y URLs
│   ├── ml/                # R2, Modal, entrenamiento y predicción
│   ├── workers/           # Aplicación Celery
│   ├── scripts/           # Seed y utilidades
│   └── docs/              # Documentación backend
├── gm_frontend/
│   ├── src/api/           # Cliente HTTP y endpoints
│   ├── src/components/    # Componentes reutilizables
│   ├── src/hooks/         # Jobs, reproducción y salas
│   ├── src/pages/         # Vistas por funcionalidad
│   ├── src/router/        # Rutas y guards
│   ├── src/services/      # Firebase y FCM
│   └── src/store/         # Estado global Zustand
├── gm_mobile/             # Aplicación Flutter
├── docker-compose.yml
├── .env.example
└── README.md
~~~

Dominios principales del backend: users, songs, stems, karaoke, mix, credits, community, playlists, notifications, recommendations y reports.

---

# 5. Requisitos previos

| Herramienta | Requerido | Función |
|---|:---:|---|
| Git | Sí | Obtener el repositorio. |
| Docker Engine | Sí | Ejecutar contenedores. |
| Docker Compose V2 | Sí | Administrar servicios. |
| Python 3.12 | Ejecución local | Backend y modelo de recomendaciones. |
| Node.js 22 y npm | Ejecución local | Frontend fuera de Docker. |

~~~bash
git --version
docker --version
docker compose version
~~~

Docker Compose contiene las dependencias de Python y Node.js necesarias para el entorno principal.

---

# 6. Variables de entorno

MusicAI utiliza un único .env global en la raíz. La plantilla se encuentra en .env.example.

~~~bash
cp .env.example .env
~~~

| Grupo | Variables principales |
|---|---|
| PostgreSQL | DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST. |
| Django | DJANGO_SECRET_KEY, DEV_DEBUG, DEV_ALLOWED_HOSTS. |
| Redis/Celery | REDIS_URL, CELERY_TASK_ALWAYS_EAGER. |
| R2 | R2_ENDPOINT, R2_REGION, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_DOCUMENTS_BUCKET. |
| Modal | Endpoints, MODAL_KEY, MODAL_SECRET y timeouts. |
| Firebase | Variables VITE_FIREBASE_* y credenciales Admin. |
| Stripe | Claves secreta, pública y webhook. |
| Gemini/audio | GEMINI_API_KEY y FFMPEG_PATH. |

Docker Compose distribuye las variables globales entre Django, Celery y React.

---

# 7. Instalación y ejecución

~~~bash
git clone <URL_DEL_REPOSITORIO>
cd musical-system
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
~~~

El contenedor backend ejecuta automáticamente las migraciones y el seed idempotente antes de iniciar Django.

~~~bash
docker compose ps
docker compose logs -f backend
docker compose down
~~~

El comando down conserva los volúmenes. La opción down -v también elimina los datos locales de PostgreSQL y Redis.

---

# 8. Servicios Docker

| Servicio | Tecnología | Puerto local | Puerto interno |
|---|---|---:|---:|
| postgres | PostgreSQL 16 | 56432 | 5432 |
| redis | Redis 7 | interno | 6379 |
| backend | Django | 8000 | 8000 |
| celery-worker | Celery | interno | — |
| celery-beat | Celery Beat | interno | — |
| frontend | React/Vite | 5173 | 5173 |

~~~bash
docker compose up -d
docker compose restart backend
docker compose restart frontend
docker compose logs -f celery-worker
docker compose logs -f celery-beat
docker compose exec backend sh
~~~

El perfil tools contiene operaciones auxiliares como el seed:

~~~bash
docker compose --profile tools run --rm seed
~~~

---

# 9. Acceso a la aplicación

| Servicio | Dirección |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000/api/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| OpenAPI | http://localhost:8000/api/schema/ |
| PostgreSQL | localhost:56432 |

El frontend utiliza /api y Vite lo redirige hacia el servicio backend dentro de la red Docker.

---

# 10. Entorno de desarrollo

## 10.1 Backend local

~~~bash
cd gm_backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py check
python manage.py runserver
~~~

.venv-modal está reservado para los servicios de Modal.

## 10.2 Frontend local

~~~bash
cd gm_frontend
npm install
npm run dev
~~~

## 10.3 Modelo de recomendaciones

El modelo se genera en dos etapas y en este orden. La primera genera el CSV; la segunda lo utiliza para entrenar music_classifier.pkl.

Con Docker Compose:

~~~bash
# Etapa 1: dataset sintético.
docker compose exec backend python ml/dataset_generator.py

# Etapa 2: entrenamiento del modelo.
docker compose exec backend python ml/train_model.py
~~~

Archivos generados:

~~~text
gm_backend/ml/data/dataset_sintetico.csv
gm_backend/ml/models/music_classifier.pkl
~~~

El dataset puede ocupar aproximadamente 1 GB. El modelo es opcional y se utiliza en /api/recommendations/for-you/ y /api/recommendations/suggested-tags/.

Ejecución local equivalente:

~~~bash
cd gm_backend
source .venv/bin/activate
python ml/dataset_generator.py
python ml/train_model.py
~~~

## 10.4 Comprobaciones

~~~bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py test
docker compose run --rm --no-deps frontend npm run build
git diff --check
~~~

---

# 11. Solución de problemas

## Docker o Compose no disponible

~~~bash
docker info
docker compose version
~~~

El servicio Docker Engine debe estar activo.

## Variables faltantes

~~~bash
ls -la .env
docker compose config --quiet
~~~

La configuración debe partir de .env.example y conservar los nombres esperados por docker-compose.yml.

## Backend o PostgreSQL no inicia

~~~bash
docker compose ps backend postgres
docker compose logs --tail=100 backend
docker compose logs --tail=100 postgres
~~~

Las causas habituales son PostgreSQL no saludable, variables incompletas o migraciones pendientes.

## Frontend no responde

~~~bash
docker compose ps frontend
docker compose logs --tail=100 frontend
docker compose restart frontend
~~~

El frontend depende del backend y utiliza el proxy /api de Vite.

## Modelo no disponible

~~~bash
docker compose exec backend ls -lh ml/models/music_classifier.pkl
docker compose exec backend python -c "from ml.predictor import is_model_available; print(is_model_available())"
~~~

El resultado esperado es True. Si el archivo no existe, ejecutar primero dataset_generator.py y luego train_model.py.

## Integraciones externas

La generación musical, R2, Stripe y Firebase requieren sus variables y endpoints. Los errores aparecen en los logs:

~~~bash
docker compose logs -f backend celery-worker frontend
~~~

## Puertos ocupados

~~~bash
ss -ltnp | grep -E ':5173|:8000|:56432'
~~~

Los puertos publicados se pueden modificar mediante las variables globales y luego reconstruir los servicios.

---

## Documentación relacionada

- Backend: gm_backend/README.md
- Frontend: gm_frontend/README.md
- Contrato API: gm_backend/docs/03_API_CONTRACT.md
- Especificación de interfaz: gm_frontend/docs/ui-specification.md
- Guía de Modal: Guia_Modal_Musical_System_Equipo.md
