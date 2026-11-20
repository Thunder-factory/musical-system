# Guía de configuración de Modal — Musical System

**Objetivo:** configurar una cuenta propia de Modal, instalar la herramienta en Windows o Linux, desplegar Musical System y obtener las cinco URLs y los dos valores de autenticación necesarios para realizar pruebas.

## 1. Crear una cuenta

1. Acceder a https://modal.com/.
2. Seleccionar **Sign up** y completar el registro.
3. Entrar en el panel de Modal (Dashboard).
4. Consultar los créditos disponibles
5. Agregar un metodo de pago

## 2. Preparar el proyecto y Python 3.12

| Elemento | Configuración |
| --- | --- |
| Python | 3.12.x |
| Carpeta del entorno virtual | `.venv-modal` |
| Carpeta de trabajo | `gm_backend` |
| Aplicación de Modal | `gm-music-server` |
| Archivo de despliegue | `ml/modal_music_server.py` |

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

### Linux (Ubuntu y distribuciones compatibles)

Abrir una terminal:

```bash
cd /ruta/al/proyecto/gm_backend
python3.12 --version
python3.12 -m venv .venv-modal
source .venv-modal/bin/activate
python --version
```

Se espera que el último comando indique `Python 3.12.x`. Si el sistema no encuentra `python3.12` o no puede crear el entorno virtual, primero se debe instalar Python 3.12 y su soporte de `venv`.

### Windows (PowerShell)

Instalar Python 3.12 desde https://www.python.org/downloads/ si aún no está instalado. Abrir **PowerShell** en la carpeta del backend:

```powershell
cd C:\ruta\al\proyecto\gm_backend
py -3.12 --version
py -3.12 -m venv .venv-modal
.\.venv-modal\Scripts\Activate.ps1
python --version
```

Se espera `Python 3.12.x`. Si PowerShell impide activar el entorno por su política de ejecución, ejecutar **solo en esa sesión**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv-modal\Scripts\Activate.ps1
```

## 3. Instalar Modal

En el directorio `gm_backend/`

Con el entorno virtual `.venv-modal` activado, los comandos son iguales en Windows y Linux:

```bash
python -m pip install --upgrade pip
python -m pip install modal==1.6.4
python -m pip show modal
modal --version
```

## 4. Iniciar sesión desde la terminal

Con el entorno virtual activo `.venv-modal`:

```bash
modal setup
```

1. Se abrirá el navegador o ingresar al link para autorizar Modal.
2. Iniciar sesión con la **cuenta registrada**.
3. Confirmar la autorización.
4. Regresar a la terminal y verificar:

```bash
modal token info
```


## 5. Preparar los requisitos de Modal

> con el entorno activo `.venv-modal`

crear el archivo temporalmente para el modal linux/windows
```bash
umask 077
grep '^R2_' ../.env > .env.modal-r2
```

```bash
Get-Content ..\.env \| Where-Object { $_ -match '^R2_' } \| Set-Content .env.modal-r2
```

Crear el secreto en Modal
```bash
modal secret create music-gen-secret --from-dotenv .env.modal-r2
```

Verificar la creacion

```bash
modal secret list
```
> Resultado: `music-gen-secret`

Eliminar archivo temporal linux/windows
```bash
rm .env.modal-r2
```

```bash
Remove-Item .env.modal-r2
```

## 6. Crear un Proxy Token

Desde gm_backend/ con el entorno activo `.venv-modal`:
```bash
modal workspace proxy-tokens create --name musical-system-backend
```
Guardar los dos valores que muestra Modal:

- **Token ID**, con prefijo `wk-`: corresponde a `MODAL_KEY`.
- **Token Secret**, con prefijo `ws-`: corresponde a `MODAL_SECRET`.


Verificar la creacion
```bash
modal workspace proxy-tokens list
```
> resultado: musical-system-backend

Cargar las variables:
```text
MODAL_KEY=
MODAL_SECRET=
```


## 7. Desplegar la aplicación

Situarse en `gm_backend` y asegurarse de que `.venv-modal` siga activado.

**Linux:**

```bash
cd /ruta/al/proyecto/gm_backend
source .venv-modal/bin/activate
modal deploy ml/modal_music_server.py
```

**Windows (PowerShell):**

```powershell
cd C:\ruta\al\proyecto\gm_backend
.\.venv-modal\Scripts\Activate.ps1
modal deploy ml/modal_music_server.py
```

Esperar a que Modal confirme el despliegue. La primera ejecución puede necesitar construir imágenes y preparar recursos. No cerrar la terminal durante el despliegue.

Para comprobar la aplicación:

```bash
modal app list
modal app info gm-music-server
```


## 8. Copiar las cinco URLs

Al finalizar el despliegue, Modal mostrará las URLs de los endpoints. También pueden consultarse en el Dashboard de la aplicación desplegada.

> Revisar
Identificar cada función y copiar su URL completa:

| Variable | Función correspondiente |
| --- | --- |
| `MODAL_ENDPOINT_FROM_DESCRIPTION` | `generate_from_description` |
| `MODAL_ENDPOINT_WITH_LYRICS` | `generate_with_lyrics` |
| `MODAL_ENDPOINT_FROM_DESCRIBED_LYRICS` | `generate_with_described_lyrics` |
| `MODAL_ENDPOINT_SEPARATE_STEMS` | `separate_stems` |
| `MODAL_ENDPOINT_FACESWAP` | `face_swap` |

Las URLs son diferentes entre workspaces. No utilizar las URLs de otra persona si se desea que las ejecuciones se carguen al workspace propio.


## 9. Comprobar el despliegue y el consumo

```bash
modal app info gm-music-server
modal app logs gm-music-server
```

- Comprobar en el Dashboard que la aplicación está desplegada y aparecen las funciones esperadas.
- Revisar la sección de uso y facturación del workspace para controlar el consumo.
- Las nuevas ejecuciones utilizan el workspace al que pertenecen los endpoints invocados. Cambiar el perfil de la CLI **no cambia por sí solo** los endpoints ya configurados en otra aplicación.

## 10. Face Swap (FaceFusion)

"Cambiar caras" corre en la misma aplicación `gm-music-server`: `ml/modal_music_server.py` importa `ml/modal_faceswap_server.py`, así que se despliega con el **mismo** comando del paso 7:

```bash
modal deploy ml/modal_music_server.py
```

> **No** desplegar `ml/modal_faceswap_server.py` por separado: reemplazaría la aplicación `gm-music-server` sin las funciones de música ni de separación de pistas.

- La primera vez se construye una imagen CUDA (≈ 10 min). En el primer job FaceFusion descarga sus modelos al Volume `gm-faceswap-models`, por lo que ese job tarda más; los siguientes reutilizan la cache.
- Copiar la URL de la función `face_swap` en `MODAL_ENDPOINT_FACESWAP` (tabla del paso 8). La misma URL sirve para enviar el job y para consultar su estado (`action: "status"`).
- Recursos que crea: Dict `gm-faceswap-job-status` (estado de los jobs), Volume `gm-faceswap-models` (pesos) y una GPU T4 (configurable con `FACESWAP_GPU`). Usa el mismo Secret `music-gen-secret` (variables `R2_*`) para leer la foto y el video y subir el resultado a `faceswap/results/`.
- Tiempos de referencia en T4 con la configuración vigente (variante C: hyperswap + expression_restorer, ver `gm_backend/docs/faceswap_spec.md` §12): ~5 min para una plantilla de 8 s a 720p y ~8-9 min para un clip de 15 s. Como máximo corren 2 contenedores a la vez; el resto espera en cola.
- El primer job después de un deploy descarga también los modelos de hyperswap, LivePortrait, oclusión y parsing de la cara, así que tarda unos minutos más.

### 10.1 Probar en local sin desplegar (`modal serve`)

Para desarrollo se puede servir solo el worker de caras de forma temporal, sin `modal deploy`:

```bash
cd gm_backend
uvx --from modal==1.6.4 --with boto3 --with pydantic modal serve ml/modal_faceswap_server.py
```

- Imprime una URL fija que termina en `-face-swap-dev.<región>.modal.run`; va en `MODAL_ENDPOINT_FACESWAP`. Es la misma cada vez que se vuelve a levantar.
- Hace falta el Secret `music-gen-secret` y un Proxy Token (pasos 5 y 6) en la cuenta donde se sirve.
- Solo existe mientras el comando está corriendo. Si la PC se suspende o se corta la red, la app queda en `APP_STATE_STOPPED` y los jobs se quedan en cola: hay que volver a levantarlo (Celery reintenta el envío).
- Recarga solo al guardar cambios en el archivo (eso puede cortar un job en curso).
- Con `modal serve` se puede servir el archivo por separado porque no reemplaza ninguna app desplegada; la advertencia de arriba aplica solo a `modal deploy`.
- Celery debe reiniciarse después de actualizar el backend para que registre las tareas `apps.faceswap.tasks.*`.

| Problema | Comprobación |
| --- | --- |
| `Failed to initialize CUDNN Frontend` en los logs | La imagen debe incluir el parche de la T4 sobre `facefusion/execution.py` (paso `sed` + `grep` de la imagen); reconstruirla con un nuevo deploy |
| El job falla con "No se detectó una cara en la foto o en el video." | Usar una foto frontal y nítida; en plantillas, revisar que `ref_time_s` apunte a un segundo donde la cara se vea sola. Los créditos se liberan |
| El job se queda en `queued` | Ver `modal app logs gm-music-server`; puede haber 2 contenedores ocupados o un arranque en frío |

## Problemas frecuentes

| Problema | Comprobación |
| --- | --- |
| No se encuentra `python3.12` o `py -3.12` | Instalar Python 3.12 y volver a verificar la versión |
| No se puede activar `.venv-modal` en PowerShell | Aplicar la instrucción de política de ejecución del paso 2 |
| `modal` no se reconoce | Activar el entorno virtual e instalar Modal dentro de él |
| `modal deploy` indica que no hay autenticación | Ejecutar `modal setup` y comprobar `modal profile current` |
| Falta `music-gen-secret` | Comprobar `modal secret list` y crear el Secret requerido en el workspace propio |
| No aparece una de las cinco URLs | Revisar la salida del despliegue, el código actualizado y el Dashboard |
| Las solicitudes HTTP devuelven error de autenticación | Revisar que `MODAL_KEY` y `MODAL_SECRET` sean Proxy Tokens del workspace correspondiente |

## Documentación oficial

- Primeros pasos: https://modal.com/docs/guide
- Despliegue: https://modal.com/docs/cli/latest/deploy
- Perfiles: https://modal.com/docs/cli/latest/profile
- Proxy Tokens: https://modal.com/docs/cli/latest/workspace
