# Evaluación de la fase 4 (machine learning)

Fecha: 2026-11-19. Dos preguntas:

1. ¿Hay un detector de melodía mejor que basic-pitch para tarareos?
2. ¿"Mejorar con IA" (ACE-Step audio2audio) respeta el estilo pedido y la melodía?

---

## 1. Detectores de melodía

**Herramienta:** `gm_tarareo/evaluacion/` (`comparar_detectores.py`, `sinteticos.py`, `detectores.py`). Resultados crudos en `gm_tarareo/evaluacion/resultados/detectores.json`.

**Por qué tarareos sintéticos:** los 11 tarareos reales de `tests/audio` no tienen las notas anotadas, así que no hay "respuesta correcta" contra la cual medir precisión. Se generaron **40 tarareos** con notas conocidas que imitan lo difícil de un tarareo real: desafinación por nota (±25 cents), vibrato, glissando entre notas, timbre de "mmm", respiración, ruido de fondo (SNR 12-30 dB) y voces graves y agudas. Son deterministas (semilla 2026).

**Detectores comparados** (todos con licencia comercial):

| Detector | Tipo | Licencia |
|---|---|---|
| basic-pitch (actual) | CNN audio → notas (Spotify) | Apache 2.0 |
| CREPE (torchcrepe, `full`) | CNN de f0 | MIT |
| FCPE (torchfcpe) | f0 rápido, familia RMVPE | MIT |
| pYIN (librosa) | probabilístico clásico, sin red | ISC |

A los tres de f0 se les aplica el mismo segmentador f0 → notas. Después, todos pasan por **la misma limpieza del worker** (`limpieza.py`).

**Métrica principal:** F1 de notas de `mir_eval`, con altura ±50 cents e inicio ±100 ms, sin exigir el final (en un tarareo los finales son difusos). También: F1 exigiendo el final, precisión de altura por cuadro (RPA), notas detectadas por nota real y tiempo de CPU.

### Resultados (40 sintéticos)

| Detector / etapa | F1 | Precisión | Recall | F1 con final | RPA | Notas / reales | CPU s por s de audio |
|---|---|---|---|---|---|---|---|
| basic-pitch crudo | 0.49 | 0.35 | 0.88 | 0.14 | 0.91 | **2.72** | 0.04 |
| **basic-pitch + limpieza (producción)** | **0.80** | 0.87 | 0.75 | 0.69 | **0.91** | 0.88 | **0.04** |
| CREPE + limpieza | 0.82 | 0.93 | 0.76 | 0.69 | 0.89 | 0.83 | **7.36** |
| FCPE + limpieza | 0.81 | 0.91 | 0.74 | 0.67 | 0.89 | 0.84 | 0.06 |
| pYIN + limpieza | 0.81 | 0.91 | 0.75 | 0.70 | 0.86 | 0.82 | 0.51 |

Por registro y con ruido (F1):

| | Grave | Agudo | Ruidoso (SNR < 18 dB) |
|---|---|---|---|
| producción | 0.79 | 0.81 | 0.80 |
| CREPE | 0.85 | 0.80 | 0.81 |
| FCPE | 0.82 | 0.79 | 0.80 |
| pYIN | 0.85 | 0.78 | 0.83 |

### Tarareos reales (10 válidos; `01 T` se rechaza por durar 4.8 s)

| Detector | Notas crudas | Notas tras limpieza | Coincidencia con producción (F1) | CPU s por s |
|---|---|---|---|---|
| basic-pitch | 27.6 | 15.4 | 1.00 | 0.03 |
| CREPE | 24.3 | 18.8 | 0.55 | 8.13 |
| FCPE | 35.4 | 24.4 | 0.44 | 0.05 |
| pYIN | 19.5 | 15.8 | 0.53 | 0.49 |

### Conclusiones

- **La limpieza del worker es la que hace el trabajo:** basic-pitch crudo devuelve 2.7 notas por cada nota real (F1 0.49). Con las 4 reglas de `limpieza.py` pasa a 0.88 (F1 0.80). Esto valida con números el problema "30 notas donde había 15" que motivó esas reglas.
- **Las alternativas mejoran solo 1-2 puntos de F1** (0.81-0.82 contra 0.80), una diferencia chica para 40 muestras. Además, el segmentador de las alternativas es nuestro, no el de producción.
- **CREPE es 175 veces más lento** (~2 minutos de CPU por un tarareo de 17 s): no sirve para un worker sin GPU.
- **FCPE** tiene la misma velocidad, pero en los tarareos reales fragmenta mucho más (24 notas contra 15) y sumaría PyTorch (~0.5-2 GB) a la imagen.
- **pYIN** no agrega dependencias (librosa ya está) y rinde algo mejor en voces graves y con ruido, pero es 12 veces más lento y no supera a producción en promedio.

**Decisión: se mantiene basic-pitch + limpieza.** Si en el futuro hay quejas con voces graves o grabaciones ruidosas, la idea más barata es usar pYIN como segunda opinión solo en esos casos (el worker ya usa YIN en `interpretacion.py`).

**Límites:** el sintetizador no reproduce consonantes, cambios de vocal ni la variedad de micrófonos reales. Para una medición definitiva habría que anotar a mano las notas de 20-30 tarareos reales.

---

## 2. "Mejorar con IA": estilo y melodía (CLAP)

**Herramienta:** `gm_backend/ml/evaluar_mejoras.py` (pasos `generar` y `medir`).

- **Estilo:** CLAP (`laion/clap-htsat-unfused`) compara el audio con el texto de los 18 estilos del catálogo. Se informa el **puesto** del estilo pedido (1 = el más parecido) y qué estilo quedó primero.
- **Melodía:** similitud de croma alineada con DTW contra la versión de referencia (1 = mismas notas y acordes).
- **Variedad:** distancia CLAP audio↔audio entre los estilos de un mismo tarareo.

Se generaron en Modal **35 mejoras** (2 tarareos, estilos cumbia, rock, jazz y huayno, varias fidelidades) más 4 de control, a unos 13 s cada una con la A100 encendida.

### Resultados (`mi_tarareo`, 4 estilos por fidelidad)

| Fidelidad (`ref_audio_strength`) | Puesto medio del estilo pedido (de 18) | Estilo que quedó 1.º (los 4 iguales) | Croma vs referencia | Variedad entre estilos |
|---|---|---|---|---|
| 0.15 | 8.0 | balada | 0.82 | 0.059 |
| 0.25 | 10.0 | balada / orquestal | 0.83 | 0.008 |
| 0.35 | 8.5 | huayno | 0.83 | 0.009 |
| 0.45 | 7.8 | trap | 0.83 | 0.004 |
| 0.55 (media, actual) | 7.8 | reggaeton | 0.83 | **0.001** |
| 0.70 (alta) | — | jazz (la referencia) | 0.85 | 0.001 |

Control con los mismos 4 prompts en **texto→música, sin referencia:** variedad **0.18**, rock 1.º y jazz 2.º, cumbia 12.º y huayno 15.º.

Comprobación directa: con fidelidad media, la onda de "cumbia" y la de "rock" tienen correlación **0.77**, es decir, son casi el mismo audio.

### Conclusiones

- **La melodía se conserva bien** con cualquier fidelidad (croma 0.82-0.85).
- **El estilo pedido casi no influye en audio2audio:** en cada fidelidad, los 4 estilos salen sonando al mismo género, y la variedad es entre 3 y 180 veces menor que en texto→música. Los prompts sí funcionan sin referencia, así que el límite es el modo audio2audio de **ACE-Step v1**, que se queda con el carácter de la referencia.
- Hoy "Mejorar con IA" **produce la canción con sonido realista**, pero **no la cambia de estilo**.
- CLAP reconoce bien rock y jazz, pero **no cumbia ni huayno**: para géneros regionales hay que juzgar de oído.
- De paso se corrigió un error: en modo referencia el servidor agregaba "English vocals, English lyrics" al prompt de una pieza instrumental.

### Opciones

1. **ACE-Step 1.5 en modo cover:** pensado justamente para rehacer una canción en otro estilo conservando melodía y estructura (MIT). Requiere una imagen nueva en Modal y repetir esta evaluación.
2. **Renombrar a "Producir con IA":** sin selector de estilos, solo calidad de producción, que es lo que hoy cumple.
3. **Híbrido:** el estilo lo pone el arreglo del worker (sus 7 estilos) y ACE-Step solo produce el sonido. Así no se prometen estilos que no salen.

Audios para comparar de oído en `pruebas-audio/` (`clap-*.mp3`).

---

### Prueba con ACE-Step 1.5 (modo cover)

Se probó primero en una app de laboratorio aparte (ACE-Step 1.5 MIT con commit fijado, DiT `acestep-v15-turbo`, sin el LM auxiliar, GPU **A10G**), con los mismos tarareos, estilos y métricas. La fuerza es `audio_cover_strength` (1.0 = muy fiel).

| Motor | Fuerza | Puesto medio del estilo pedido (de 18) | Estilos en el top 4 | Croma vs referencia | Variedad entre estilos | Tiempo por mejora |
|---|---|---|---|---|---|---|
| v1 audio2audio (A100) | 0.55 (actual) | 7.8 | 1 de 4 | 0.83 | 0.001 | ~13 s |
| v1 audio2audio (A100) | 0.15 | 8.0 | 0 de 4 | 0.82 | 0.059 | ~13 s |
| **1.5 cover (A10G)** | 0.8 | **2.8** | 3 de 4 | 0.82 | **0.175** | **~9 s** |
| **1.5 cover (A10G)** | 0.5 | **2.8** | 3 de 4 | 0.82 | **0.180** | **~9 s** |
| **1.5 cover (A10G)** | 0.3 | **2.8** | 3 de 4 | 0.83 | **0.186** | **~9 s** |
| **1.5 cover (A10G)** | 0.2 | **2.5** | 3 de 4 | 0.84 | **0.197** | **~9 s** |
| control texto→música (sin referencia) | — | — | 2 de 4 | — | 0.18 | — |

Por estilo (`mi_tarareo`, todas las fuerzas): **jazz y huayno quedan 1.º**, rock 3.º y cumbia 5.º-6.º. CLAP reconoce mal la cumbia incluso en texto→música, así que esa hay que juzgarla de oído. Con `t05` y fuerza 0.5: jazz 1.º, rock 3.º, huayno 7.º y cumbia 13.º.

**Conclusión:** el modo cover de 1.5 **sí cambia el estilo**. La variedad entre estilos es igual a la de texto→música (0.18-0.20, contra 0.001 de v1) y el estilo pedido sube del puesto ~8 al ~2.7, **conservando la melodía igual que v1** (croma 0.82-0.85). Además es más rápido y corre en una GPU más barata (A10G en lugar de A100). La fuerza casi no cambia los resultados en el rango 0.2-0.8; las de 0.2-0.3 dan algo más de croma y de variedad.

Muestras: `pruebas-audio/v15-mi_tarareo-*-0.5.mp3` (comparar con `clap-mi_tarareo-*-0.55.mp3` de v1).

**Decisión (2026-11-19): integrado.** "Mejorar con IA" usa ahora `CoverServer` (ACE-Step 1.5 cover) en `gm-music-server`, con fidelidades alta 0.8 · media 0.5 · libre 0.2. El audio se sube como MP3 de 192 kbps porque las subidas multiparte de WAV a R2 fallaban a veces con `ServiceUnavailable`.

## 3. LoRA andino (preparado, no entrenado)

No hay dataset con permiso de uso, así que no se entrenó. Para hacerlo más adelante:

- **Datos:** 50-200 canciones de huayno, morenada y caporales con permiso explícito (propias o con licencia), cortadas en fragmentos de 30-60 s, con tags en el formato del prompt (`andean folk, huayno, charango, quena, ...`).
- **Entrenamiento:** el repo de ACE-Step trae un script de LoRA. En Modal, en una A100 con un Volume para el dataset y los pesos, son unas horas de GPU. El LoRA resultante se carga con `lora_name_or_path`, que la versión fijada ya soporta.
- **Evaluación:** repetir `evaluar_mejoras.py` con y sin el LoRA y juzgar de oído, porque CLAP no reconoce bien estos géneros.
- **Regla del worker:** su `CLAUDE.md` dice "no entrenamos ningún modelo". El LoRA viviría en Modal, no en el worker, pero conviene acordarlo con el equipo.
