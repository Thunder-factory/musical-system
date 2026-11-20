# Worker de Tarareo → Canción

Worker Python que recibe un tarareo y genera canciones instrumentales. Es una de las 5
funcionalidades del sistema (ver [CLAUDE.md](CLAUDE.md) para el contexto
completo del proyecto y el contrato con el resto del equipo).

Extrae la melodía, infiere pulso, tonalidad, acordes y estilos, y produce MIDI,
MP3 y partitura MusicXML. La demo ofrece muestras cortas y completa las
versiones que el usuario pide, conservándolas para volver a escucharlas.

## Setup

Requiere **Python 3.11** (`basic-pitch` no soporta 3.12+) y `ffmpeg` en el
PATH. El render necesita FluidSynth y un SoundFont con licencia compatible;
ver [LICENCIAS.md](docs/LICENCIAS.md). Docker instala estos componentes.

```bash
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python probar_entorno.py
```

`probar_entorno.py` valida que todo el stack (ffmpeg, basic-pitch,
librosa, etc.) esté bien instalado antes de seguir.

## Uso

### Iterar rápido sin levantar el servidor

```bash
python probar.py tests/audio/mi_tarareo.wav
```

Corre las etapas 1–8 y deja canciones MP3, arreglos MIDI, `melodia.mid`,
`partitura.musicxml` y `analisis.json` en `salidas/prueba-<nombre>/`.

### Grabar y comparar estilos en el navegador (PowerShell)

```powershell
$env:TARAREO_MODO_DESARROLLO="true"
venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Abrir `http://localhost:8000/demo`: grabar, comparar muestras y pulsar
**Escuchar completa** en las versiones que se quieran. **Elegir como favorita**
es independiente. Las completas se reutilizan sin repetir la IA ni el render.
La partitura se abre en MuseScore para editar o imprimir.

También se puede abrir la demo en Docker:

```powershell
docker compose -f docker-compose.demo.yml up -d --build
```

Abrir `http://localhost:8004/demo`. Las salidas se conservan en un volumen
de Docker para evitar el costo de escribir audio en una carpeta compartida
de Windows. Se descargan desde la página.

La masterización suave y la expresión del tarareo están activadas por defecto.
Los siete estilos incorporan capas de instrumentos por sección y un clima
musical sugerido que ajusta el apoyo sin cambiar la melodía. Ver
[CLIMA-E-INSTRUMENTOS.md](docs/CLIMA-E-INSTRUMENTOS.md).
La interpretación contrasta las alturas con el audio, modera la expresión
y conserva mejor el ritmo libre; ver
[INTERPRETACION-TARAREO.md](docs/INTERPRETACION-TARAREO.md).
Detalles del flujo y su contrato con Django/R2:
[MUESTRAS-Y-VERSIONES.md](docs/MUESTRAS-Y-VERSIONES.md).

### Levantar el servidor

```bash
uvicorn app.main:app --reload
```

- `POST /procesar` — encola un job (contrato completo en CLAUDE.md)
- `GET /salud` — estado del worker
- `GET /jobs/{id}` — estado/resultado de un job

Configuración por variables de entorno: ver [.env.example](.env.example)
y `app/config.py` (umbrales de duración, silencio, limpieza de notas,
etc. — todos calibrables sin tocar código).

## Tests

```bash
pytest -m "not slow"   # rápido, para iterar (excluye lo que corre basic-pitch de verdad)
pytest                 # suite completa (incluye inferencia, render y pruebas de integración)
```

Los fixtures de audio inválido (silencio, ruido blanco, grabación corta)
se generan con `ffmpeg` al vuelo en `tests/conftest.py`. El único audio
versionado es `tests/audio/mi_tarareo.wav`, un tarareo real usado como
caso de referencia para calibrar la limpieza de notas.
