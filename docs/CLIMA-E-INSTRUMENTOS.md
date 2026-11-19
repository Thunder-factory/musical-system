# Clima musical e instrumentación de los siete estilos

El trabajador mantiene la elección automática del estilo y sus alternativas.
Las nuevas capas refuerzan cada arreglo y se generan en CPU con el SoundFont
actual. No se entrena ni se descarga otro modelo.

## Clima musical sugerido

`pipeline/clima.py` combina tempo, densidad, rango, saltos, articulación y modo
para sugerir sereno, melancólico, luminoso, enérgico o intenso. El modo menor
no significa automáticamente tristeza: también puede producir un arreglo
enérgico. No se usa el volumen del micrófono para atribuir una emoción.

Es una decisión compositiva por reglas, no una detección del estado emocional
de quien canta. `confianza` expresa la separación entre reglas; no es una
probabilidad calibrada con oyentes. Con margen menor de 0.05 se declara
`ambiguo` y el motivo menciona el segundo clima posible. Estos umbrales son
iniciales: necesitan más validación auditiva con tarareos reales.

La intensidad sugerida modifica suavemente las velocidades del apoyo
(factor entre 0.78 y 1.08), sin cambiar tempo, alturas ni tiempos de la melodía.
El clima se calcula con los mismos rasgos originales para todas las versiones;
no depende del estilo de la alternativa.

## Instrumentos de apoyo

Se conserva la base de melodía, acompañamiento, bajo y batería de cada estilo.
Las capas ampliadas reemplazan el colchón anterior, para evitar acumular pistas.

| Estilo | Primer color | Segundo color |
|---|---|---|
| Balada | Cuerdas suaves | Guitarra acústica |
| Pop | Guitarra limpia | Detalles de sintetizador |
| Rock suave | Órgano | Guitarra limpia |
| Lo-fi | Guitarra jazz | Vibráfono |
| Folk | Violín | Flauta |
| Épico | Trompas | Coro instrumental |
| Electrónico | Arpegio de sintetizador | Pad atmosférico |

En balada luminosa las cuerdas pueden pasar a piano eléctrico; el electrónico
sereno o melancólico usa un arpegio cristalino; el épico enérgico o intenso
cambia el coro por timbales orquestales. Si un instrumento ya está en la base,
se elige un reemplazo del mismo estilo. El nombre y programa efectivos quedan
en `arreglo.pistas`. Todos son instrumentos General MIDI del SoundFont existente.

Las nuevas notas salen de las voces de los acordes ya calculados. Los timbales
usan la fundamental del acorde; los arpegios recorren sus notas, sin introducir
otra melodía independiente.

## Entradas por sección y mezcla

- Intro y outro conservan su instrumentación anterior, sin capas nuevas.
- El verso tiene detalles del segundo color cada dos compases.
- Los estribillos tienen segunda voz y primer color.
- El puente tiene los dos colores y carece de segunda voz.

Así hay como máximo dos roles de apoyo simultáneos entre segunda voz, colchón
y nuevos colores. Las pistas base (acompañamiento, bajo y batería) se cuentan
aparte. Los colores se ubican a izquierda/derecha con volumen MIDI 54 y 50,
por debajo del acompañamiento (72) y de la melodía (120). Se conserva el
objetivo final de -16 LUFS; estos volúmenes no garantizan por sí solos el mismo
balance perceptual en todos los timbres, por lo que la escucha sigue siendo
necesaria.

## Configuración e integración

Ambos ajustes están activos por defecto en el pipeline:

```dotenv
TARAREO_ARREGLO_CLIMA_MUSICAL=true
TARAREO_ARREGLO_INSTRUMENTACION_AMPLIADA=true
```

Se pueden desactivar por separado para comparar. La API de bajo nivel
`arreglar` mantiene el comportamiento anterior si no recibe `clima` ni
`instrumentacion_ampliada=True`.

`analisis.json` incorpora `arreglo.clima` (opcional para poder leer análisis
anteriores): nombre, intensidad, confianza, ambiguo y motivo. El resultado del
job también lo expone como `metadatos.clima`. La demo muestra su explicación.
No cambian los parámetros obligatorios de Django ni las URLs de R2.

La muestra se recorta del mismo arreglo que se usa para la completa. Completar
desde el análisis guardado no vuelve a ejecutar basic-pitch. La caché local
de completas pasa a v4 e incluye ambos ajustes. Una muestra generada antes de
esta actualización corresponde al arreglo anterior: grabar o subir nuevamente
para comparar muestra y completa con la nueva instrumentación.

## Validación

`tests/test_clima_instrumentacion.py` cubre los cinco climas, menor enérgico,
ambigüedad, determinismo, conservación de melodía, duración, máximo de apoyos
simultáneos, mezcla MIDI, las 21 variantes y separación de caché por ajustes.
Las pruebas del núcleo verifican que el clima llegue al análisis y al resultado.

La demo de Docker se inicia con
`docker compose -f docker-compose.demo.yml up -d --build` y se abre en
`http://localhost:8004/demo`. Usa un volumen de Docker para las salidas;
la primera prueba con la carpeta de Windows compartida demoraba mucho más
al escribir los WAV de síntesis. Los archivos se descargan desde la demo
y permanecen en el volumen al reiniciar el contenedor.

Comprobación del 2026-11-15: 376 tests en Windows y 87 relacionados en
Docker/ONNX. Una prueba HTTP con el tarareo real produjo tres muestras en
9.75 s, completó dos versiones en 8.10 y 8.62 s y las recuperó de caché en
9 y 17 ms. Los MIDI completos fueron idénticos a los usados para sus muestras;
ambas versiones conservaron el mismo clima. Son mediciones de esta máquina,
no un compromiso de latencia para cualquier equipo.

Se renderizaron además siete muestras diagnósticas del mismo tarareo, una por
estilo, en `salidas/estilos-reforzados/`, con informe de loudness y tiempos.
Los estilos de esa comparación se forzaron exclusivamente para escuchar la
instrumentación; el flujo normal sigue ofreciendo solo los estilos que encajan.
