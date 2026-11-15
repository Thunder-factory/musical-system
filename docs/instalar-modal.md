## archivo que se desplegara esta en:

```text
musical-system/
├── gm_backend/
│   ├── ml/
│   │   └── modal_music_server.py
│   ├── config/
│   └── manage.py
├── gm_frontend/
└── docker-compose.yml
```

## ingresar a gm_backend y ejecutar

```bash
python3.12 -m venv .venv-modal
source .venv-modal/bin/activate

python -m pip install --upgrade pip
python -m pip install --upgrade modal pydantic requests boto3
modal --version
```

## registrarse en modal `https://modal.com/`
- Ingresar a `https://modal.com/` crear un cuenta y agregar un metodo de pago

- manteniendo activo .venv-modal, ejecutar:

```bash
modal setup
```
Ingresar al link para autorizar -> click en `autorize`

- En la terminal verificar

```bash
modal token info
```

## crear el secreto

crear un archivo temporal en el backend con las variables R necesarias
```bash
umask 077
grep '^R2_' ../.env > .env.modal-r2
```

> y ejecutar
`modal secret create music-gen-secret --from-dotenv .env.modal-r2`

> para eliminar el temporal
`rm .env.modal-r2`

Ejecutar este comando solo si existe un archivo .env real en el backend
```bash
modal secret create music-gen-secret --from-dotenv .env
```

valores generados

```bash
 modal secret create music-gen-secret --from-dotenv .env.modal-r2

Created a new secret 'music-gen-secret' with the keys 'R2_ACCOUNT_ID', 'R2_ENDPOINT', 'R2_REGION', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 
'R2_DOCUMENTS_BUCKET'

Use it in your Modal app:

                                                                                                                                                 
@app.function(secrets=[modal.Secret.from_name("music-gen-secret")])                                                                              
def some_function():                                                                                                                             
    os.getenv("R2_ACCOUNT_ID")                                                                                                                   
    os.getenv("R2_ENDPOINT")                                                                                                                     
    os.getenv("R2_REGION")                                                                                                                       
    os.getenv("R2_ACCESS_KEY_ID")                                                                                                                
    os.getenv("R2_SECRET_ACCESS_KEY")                                                                                                            
    os.getenv("R2_DOCUMENTS_BUCKET")              
```



## proteger endpoints de `gm_backend/ml/modal_music_server.py`

> @modal.fastapi_endpoint(method="POST")

```text
Los cuatro métodos son:
1. generate_from_description
2. generate_with_lyrics
3. generate_with_described_lyrics
4. separate_stems
```

```python
@modal.fastapi_endpoint(
    method="POST",
    requires_proxy_auth=True,
)
```

## crear un proxy Token

```bash
 ─────────────────────────────────────────────────────────────────────────── 
  Modal-Key: wk-UR1fc1pEiu1LC47qA9aU34                                       
  Modal-Secret: ws-YBHRZ7G8LLklZpVp36rUTj                                    
 ─────────────────────────────────────────────────────────────────────────── 
  Authorization: Bearer wk-UR1fc1pEiu1LC47qA9aU34.ws-YBHRZ7G8LLklZpVp36rUTj  
 ─────────────────────────────────────────────────────────────────────────── 
```

verificar
```bash
modal workspace proxy-tokens list
```

resultado
```text
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┓
┃ Name                   ┃ Token ID                  ┃ Created at           ┃ Created by ┃ Scoped ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━┩
│ musical-system-backend │ wk-UR1fc1pEiu1LC47qA9aU34 │ 2026-11-14 16:13 -04 │ wwov1997   │ False  │
└────────────────────────┴───────────────────────────┴──────────────────────┴────────────┴────────┘
```

## Desplegar ACE-Step y Demucs

asegurate de tener un metodo de pago en `modal.com`

```bash
modal deploy ml/modal_music_server.py
```

# verificar los enpoints

> Ir a functions y verificar que exitan las 4 funciones

```bash
 curl -i -X POST \
  "https://wwov1997--gm-music-server-musicgenserver-generate-with-lyrics.us-east.modal.run" \
  -H "Content-Type: application/json" \
  -d '{}'
HTTP/2 401 
alt-svc: h3=":443"; ma=2592000
date: Sat, 14 Nov 2026 20:40:11 GMT
vary: accept-encoding
content-length: 56

modal-http: missing credentials for proxy authorization

```

## llenar las variables

> MODAL_ENDPOINT_FROM_DESCRIPTION=
  MODAL_ENDPOINT_WITH_LYRICS=
  MODAL_ENDPOINT_FROM_DESCRIBED_LYRICS=
  MODAL_ENDPOINT_SEPARATE_STEMS=

> con las urls generadas de cada functions


## en una nueva terminal

verificar Celery
```bash
docker exec musical_celery_dev celery -A workers.celery inspect ping
```

Verificar las tareas de Celery
```bash
docker exec musical_celery_dev celery -A workers.celery inspect registered
```
