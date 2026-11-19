# syntax=docker/dockerfile:1
# =====================================================================
#  Worker Tarareo -> Cancion
#
#  Targets:
#    worker   (por defecto) imagen de produccion
#    pruebas  la misma imagen + pytest, tests y audios de prueba
#
#    docker build -t worker-tarareo .
#    docker build --target pruebas -t worker-tarareo:pruebas .
#
#  Base Debian 13 (trixie): de esa misma version sale el SoundFont FluidR3_GM
#  (MIT) que se usa en desarrollo, asi local y Docker suenan igual.
# =====================================================================

FROM python:3.11-slim-trixie AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg: ingesta, loudness y MP3. fluidsynth + fluid-soundfont-gm: render
# (etapa 8). Paquetes oficiales de Debian: nada se descarga a mano.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fluidsynth fluid-soundfont-gm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Backend ONNX: basic-pitch sin sus dependencias declaradas (pide TensorFlow
# en Linux); las que de verdad usa estan en requirements-docker.txt.
COPY requirements-docker.txt .
RUN pip install -r requirements-docker.txt \
    && pip install --no-deps basic-pitch==0.4.0

# Usuario sin privilegios; solo puede escribir en salidas/ y en la caché de numba.
RUN useradd --create-home --uid 10001 worker \
    && mkdir -p /app/salidas /app/.cache-numba \
    && chown worker:worker /app/salidas /app/.cache-numba

COPY app/ app/
COPY contratos/ contratos/

ENV TARAREO_MODO_DESARROLLO=false \
    TARAREO_DIRECTORIO_SALIDAS=/app/salidas \
    TARAREO_FLUIDSYNTH=fluidsynth \
    TARAREO_SOUNDFONT=/usr/share/sounds/sf2/FluidR3_GM.sf2 \
    NUMBA_CACHE_DIR=/app/.cache-numba

USER worker

# Compila de antemano lo que librosa acelera con numba y lo deja guardado en
# la imagen: sin esto, el primer job de cada contenedor tardaba ~85 s de más.
RUN python -m app.calentamiento

EXPOSE 8000


# ---------------------------------------------------------------------
FROM base AS pruebas

USER root
RUN pip install pytest==8.4.2 ruff==0.16.5
COPY pytest.ini probar.py ./
COPY tests/ tests/
RUN chown -R worker:worker /app/tests
# Los tests usan rutas locales en inputUrls (ver tests/conftest.py).
ENV TARAREO_MODO_DESARROLLO=true
USER worker
CMD ["python", "-m", "pytest", "-q", "-p", "no:warnings", "-p", "no:cacheprovider"]


# ---------------------------------------------------------------------
FROM base AS worker

# Un solo proceso: el limite de jobs simultaneos (TARAREO_CAPACIDAD) es por
# proceso. Para mas capacidad, mas contenedores (o subir la capacidad).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/salud', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
