# Plan de la funcionalidad Tarareo → Canción

> Plan de las etapas que faltan. Toma ideas (no código) de las dos repos de
> referencia y respeta las restricciones de CLAUDE.md: CPU, Windows, Python 3.11,
> sin entrenar modelos y licencias que permitan uso comercial.

## 1. Qué tomamos de las dos repos de referencia

| | ianiv/YuE2 | timoncool/YuE2-Studio |
|---|---|---|
| Qué es | Studio FastAPI sobre mlx-YuE (YuE2-3B en MLX) | App de escritorio Rust + React/Tauri sobre yue2.cpp |
| Hardware | **Solo Apple Silicon** | Windows con **NVIDIA ≥ 6 GB** (en CPU es "many times slower") |
| Licencia de los pesos | **CC BY-NC 4.0** (no comercial) | **CC BY-NC 4.0**; SheetSage2, MuScriptor y otros también NC |
| Hum-to-song | Sí: tarareo → partitura ABC → condiciona la generación | No dedicado: "continuar desde partitura" con una semilla |
| ¿Adoptable? | **No** (Mac + NC + Python 3.12 + ~13 GB) | **No** (NVIDIA + otro stack + NC) |

**Ideas que sí tomamos:**

1. **Condicionar con una representación simbólica, no con audio crudo** (YuE2).
   Confirma que el JSON intermedio (melodía, BPM, tonalidad, acordes) es el
   diseño correcto. Le sumamos un exportador JSON → MIDI/MusicXML (y ABC si
   un generador futuro lo pide).
2. **Conservar la prosodia** (el "prosody adapter" de YuE2). Además de las notas
   cuantizadas, guardamos el pitch bend y el micro-timing que basic-pitch ya
   devuelve (hoy se descartan en `melodia.py`), para que el render suene
   humano y no robótico.
3. **Planificar la estructura antes de generar** (YuE2). En la etapa 7 se decide
   primero `intro → A → A' → B → A → outro` y después se llena cada sección.
4. **Tempo con beat tracking robusto** (`beat_dbn.rs` de YuE2-Studio: red + DBN).
   Nosotros lo hacemos sin modelo extra: tempo desde los **onsets de las notas
   limpias** y librosa como segunda opinión. Un tarareo no tiene percusión,
   así que el beat tracking sobre el audio crudo falla seguido.
5. **Variedad armónica** (`harmony.rs` de YuE2-Studio). Se penaliza repetir el
   mismo acorde muchos compases seguidos y se favorecen las cadencias al cerrar
   una sección.
6. **Ventana de 10-30 s** (ambas): coincide con nuestro rango de 8-30 s.

**Lo que hacemos mejor que ambas:** la limpieza de la etapa 4 (ninguna tiene
algo comparable) y los errores accionables para tarareos malos.

## 2. Etapas a construir (una por vez, cada una con sus tests)

### Etapa 5 — ANÁLISIS (`pipeline/analisis.py`), CPU

| Qué | Cómo | Por qué |
|---|---|---|
| BPM | Histograma de intervalos entre onsets de las notas limpias → candidato; `librosa.beat.beat_track` como segunda opinión; elegir el que mejor alinee los onsets a una grilla; rango 60-160 | Las notas limpias son una señal mucho más limpia que el audio de una voz sin percusión |
| Tonalidad | `music21` (Krumhansl-Schmuckler) sobre las notas **ponderadas por duración**; devolver la confianza (correlación) | La teoría ya está implementada; ponderar evita que las notas de paso cambien la tonalidad |
| Cuantización | A una grilla de 1/8 o 1/16 según el BPM, con un "snap" suave (solo si el desvío es < 30 % de la celda) | Una cuantización dura destruye la expresión del tarareo; la suave conserva la intención |
| Compás | 4/4 por defecto; 3/4 solo si la acentuación lo sugiere claramente | Detectar el compás de un tarareo es poco confiable; mejor un default honesto |

**Criterio de aceptación:** BPM a ±5 % y tonalidad correcta (o relativa) en el
lote de grabaciones de prueba, etiquetadas a mano.

### Etapa 6 — ARMONÍA (`pipeline/armonia.py`), CPU

- Un acorde por compás (o dos si el compás es denso).
- Candidatos: las tríadas diatónicas de la tonalidad (I, ii, iii, IV, V, vi).
- Puntaje = notas de la melodía que pertenecen al acorde, **ponderadas por
  duración y por tiempo fuerte** + preferencia de transición (V→I, IV→V,
  ii→V) – penalización por repetir (idea 5).
- Elección por programación dinámica (tipo Viterbi) sobre los compases, no
  acorde por acorde de forma aislada.
- Salida: completa el **JSON intermedio** (contrato estable de aquí en adelante).

### Etapa 6.5 — ESTILO INFERIDO (el usuario no elige género)

Reglas simples y explicables sobre BPM, modo, densidad de notas, rango
melódico, saltos, articulación (legato o staccato) y repetición de motivos →
un preset entre 7: `balada`, `pop`, `rock_suave`, `lofi`, `folk`, `epico`,
`electronico` (implementado 2026-11-14 como tabla de perfiles, con confianza,
alternativa y aviso de ambigüedad; bossa se descartó porque la síncopa no se
puede medir en un tarareo de ritmo libre). Se expone en `analisis.json` con el motivo
(ej. "BPM 72 + notas largas → balada"). Sin modelo: sin datos para entrenar
y con restricción de no entrenar.

### Etapa 7 — ARREGLO (`pipeline/arreglo.py`), CPU

- Plan de estructura primero (idea 3). La melodía del tarareo es la sección A;
  la sección B usa la misma progresión transportada al IV o al vi.
- Por preset: instrumentos General MIDI, patrón de batería, bajo (raíz +
  quinta), acompañamiento (acordes en bloque o arpegiados).
- Duración objetivo: 60-90 s.

### Etapa 8 — RENDER (`pipeline/render.py`), CPU

- MIDI multipista con `pretty_midi` → **FluidSynth + FluidR3_GM** (MIT;
  licencias verificadas en `docs/LICENCIAS.md`).
- Acabado ligero: reverb moderada en FluidSynth, EQ suave y compresión
  estéreo 1.3:1 en ffmpeg. Activado por defecto y desactivable con
  `TARAREO_RENDER_MASTERIZACION=false` (ver `docs/MASTERIZACION.md`).
- `ffmpeg`: medición `ebur128` + ganancia y limitador a -16 LUFS / -1 dBTP
  → MP3 192 kbps.
- Salidas: `cancion.mp3`, `melodia.mid`, `arreglo.mid`, `analisis.json`.

### Etapa 9 — GENERATIVA (opcional, GPU, después)

Evaluación de candidatos (2026-11-15, sin instalarlos ni cambiar el stack):

- **ACE-Step 1.5:** candidato para producir a partir de nuestra referencia.
  Admite referencia de audio, cover y control de metadatos musicales. El
  checkpoint principal oficial figura como MIT; fijar versión y revisar los
  archivos concretos al integrarlo. La fidelidad al tarareo requiere una
  comparación propia, no está garantizada por las capacidades declaradas.
  [Repositorio](https://github.com/ace-step/ACE-Step-1.5) y
  [pesos oficiales](https://huggingface.co/ACE-Step/Ace-Step1.5).
- **Qwen2-7B-Instruct:** modelo de texto Apache 2.0, útil opcionalmente para
  letras, títulos y descripciones de producción; no interpreta directamente
  el audio ni reemplaza la extracción de notas y ritmo.
  [Ficha oficial](https://huggingface.co/Qwen/Qwen2-7B-Instruct).
- **SDXL-Turbo:** portadas en un servicio opcional. La licencia publicada
  actualmente permite usos comerciales limitados bajo condiciones, incluido
  registro y límites de ingresos; no tratarlo como MIT/Apache.
  [Licencia oficial](https://huggingface.co/stabilityai/sdxl-turbo/blob/main/LICENSE.md).
- **Demucs:** separación de fuentes para la funcionalidad de separación del
  equipo, no para corregir el tarareo. Código MIT; repositorio original
  archivado, por lo que hay que decidir cómo mantener sus dependencias.
  [Repositorio oficial](https://github.com/facebookresearch/demucs).

Mantener estos servicios separados del worker CPU y de Django. No cargar los
cuatro modelos en cada proceso ni asumir que hace falta entrenarlos. Prioridad:
interpretación del tarareo → arreglo fiel → prueba generativa con GPU alquilada.

Antes de esta etapa se reforzó el arreglo de los siete estilos con capas
instrumentales por sección y clima musical sugerido por reglas. Implementado
sin GPU ni modelos nuevos; ver [CLIMA-E-INSTRUMENTOS.md](CLIMA-E-INSTRUMENTOS.md).

- Interfaz `Generador(json_intermedio, audio_referencia) -> audio`. FluidSynth es
  la implementación por defecto y siempre disponible.
- Candidato: **ACE-Step** en modo audio2audio, usando el render de FluidSynth
  como referencia y un prompt construido a partir del JSON (estilo inferido,
  BPM, tonalidad). **Antes de comprometerse, verificar la licencia de los pesos
  y la VRAM real**.
- Corre en un worker GPU aparte (ARQUITECTURA.md, decisión 12). Si no hay GPU,
  se entrega el render de FluidSynth.
- Descartados: YuE2 (ambas variantes), MusicGen (pesos no comerciales), Suno
  (sin API oficial).

## 3. Cambios del worker que salen del debate de arquitectura

1. Núcleo agnóstico al transporte: `ejecutar_job(sobre) -> ResultadoJob`;
   `main.py` queda como adaptador HTTP.
2. Límite de jobs simultáneos (semáforo) + `capacidad`/`ocupados` en `/salud` +
   503 si está lleno.
3. `codigoError` (`ENTRADA_INVALIDA` | `ERROR_INTERNO`) + callbacks de
   progreso con `etapa`.
4. Validar `jobId` (UUID) y permitir rutas locales/`file://` solo en modo
   desarrollo.
5. Modelo de basic-pitch cargado una sola vez al arrancar; backend ONNX al
   armar el Dockerfile (mismas notas, 48 MB en vez de 1.2 GB; requiere acordar
   el cambio de `requirements.txt`).

## 4. Orden propuesto

1. ✅ Corregir los 2 bugs de la Etapa 1 (fusión que acortaba notas; duración
   validada antes de recortar los silencios).
2. Validar la limpieza con más grabaciones (`probar.py --lote`).
3. Cambios del worker (sección 3, puntos 1-4).
4. Etapa 5 → 6 → 6.5 → 7 → 8, cada una con su OK.
5. Dockerfile + ONNX.
6. Etapa 9 (opcional).
