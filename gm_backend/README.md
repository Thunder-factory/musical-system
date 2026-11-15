# MusicAI — Backend

API REST de **MusicAI**, construida con Django REST Framework. Gestiona usuarios, canciones generadas o subidas, Karaoke, Mix DJ, créditos, comunidad y notificaciones.

## Stack

| Tecnología | Uso |
| :--- | :--- |
| Django 5 + DRF | API y lógica de negocio |
| SimpleJWT | Autenticación mediante JWT |
| PostgreSQL | Datos, usuarios, créditos y metadatos |
| Celery + Redis | Procesamiento asíncrono |
| Cloudflare R2 + boto3 | Almacenamiento privado de audio e imágenes |
| Modal | ACE-Step, Qwen, SDXL y Demucs |
| Stripe | Suscripciones y pagos |
| Firebase Admin | Notificaciones FCM y salas de Karaoke |
| Gemini | Limpieza opcional de letras transcritas |


## Desarrollo local

La ejecución principal utiliza el `docker-compose.yml` de la raíz y el `.env` global del repositorio:

```bash
docker compose up --build backend postgres redis
```

Para ejecutar comandos dentro del backend:

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py migrate
```

Para ejecutar pruebas:

```bash
docker compose exec backend python manage.py test
```

Para Celery:

Los servicios `celery-worker` y `celery-beat` se levantan desde el mismo Compose y reciben el `.env` global.

El seed es idempotente y prepara roles, superadmin, usuarios de prueba, planes, créditos y tags:

```bash
docker compose exec backend python scripts/seed_db.py
```

## Modelo local de recomendaciones

El clasificador opcional de recomendaciones se guarda en `ml/models/music_classifier.pkl`. No se incluye en el repositorio porque el dataset y el modelo son archivos generados. Solo se necesita para mejorar `For You` y las sugerencias de tags.

### Usando Docker Compose

No es necesario activar un entorno virtual. El contenedor `backend` ya contiene las dependencias de Python. Ejecuta las dos etapas en este orden; no realizan la misma operación:

```bash
# 1. Genera el dataset sintético (puede ocupar aproximadamente 1 GB).
docker compose exec backend python ml/dataset_generator.py

# 2. Lee el dataset, entrena el clasificador y crea el modelo .pkl.
docker compose exec backend python ml/train_model.py
```

`train_model.py` depende del CSV creado por `dataset_generator.py`. Los archivos se crean dentro del volumen de `gm_backend`:

```text
gm_backend/ml/data/dataset_sintetico.csv
gm_backend/ml/models/music_classifier.pkl
```

### Ejecutando localmente

Desde `gm_backend/`, activa el entorno Python del backend. Si todavía no existe, créalo e instala las dependencias:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ejecuta primero el generador y, cuando termine, entrena el modelo:

```bash
# 1. Genera el dataset sintético.
python ml/dataset_generator.py

# 2. Entrena el clasificador usando el CSV anterior.
python ml/train_model.py
```

En Windows, la activación equivalente es `.venv\\Scripts\\activate`. El entorno `.venv-modal` se reserva para los servicios de Modal y no es necesario para entrenar este clasificador.

## Configuración

El backend recibe su configuración desde el `.env` global ubicado en la raíz del repositorio. Docker Compose la distribuye entre Django, Celery y los servicios relacionados.

Variables consumidas directamente por el backend:

```env
SECRET_KEY=...
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
REDIS_URL=redis://localhost:6379/0

R2_ACCOUNT_ID=...
R2_ENDPOINT=...
R2_REGION=auto
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_DOCUMENTS_BUCKET=musical-bucket

MODAL_ENDPOINT_FROM_DESCRIPTION=...
MODAL_ENDPOINT_WITH_LYRICS=...
MODAL_ENDPOINT_FROM_DESCRIBED_LYRICS=...
MODAL_ENDPOINT_SEPARATE_STEMS=...
MODAL_KEY=...
MODAL_SECRET=...

SUPERADMIN_USERNAME=...
SUPERADMIN_PASSWORD=...
```

Variables adicionales utilizadas por módulos concretos:

```env
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
FIREBASE_PROJECT_ID=...
FIREBASE_CLIENT_EMAIL=...
FIREBASE_PRIVATE_KEY=...
FIREBASE_DATABASE_URL=...
PUSH_NOTIFICATIONS_ENABLED=False
GEMINI_API_KEY=...
```

`R2_ACCOUNT_ID` identifica la cuenta; el cliente de almacenamiento utiliza principalmente `R2_ENDPOINT`.

## Estructura

```text
gm_backend/
├── apps/             # Dominios Django: users, songs, karaoke, stems, mix, etc.
├── config/           # Settings y URLs raíz
├── ml/               # Cliente R2 e integración con Modal/IA
├── workers/          # Aplicación y configuración de Celery
├── scripts/          # Seed idempotente y utilidades operativas
└── docs/             # Contratos y documentación técnica
```

## Documentación y reglas

- [`docs/01API_CONTRACT.md`](docs/01_API_CONTRACT.md): contrato de endpoints para frontend y clientes.
- La lógica de negocio debe permanecer en servicios; las views deben delegar y responder.
- Las tareas largas deben ejecutarse mediante Celery.
- Usa `AUTH_USER_MODEL = 'users.User'` y los permisos compartidos de `apps.core`.
- Conserva `BaseModel` y su soft delete para los modelos de negocio.
- No modifiques contratos de API, credenciales ni archivos `.env` dentro del repositorio.
