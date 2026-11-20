# Comparar estilos y escuchar versiones completas

## Flujo recomendado

1. `POST /procesar` con `operacion: "muestras"` y el tarareo en `inputUrls`.
   Se extraen las notas y el contexto musical una sola vez. Se entregan hasta
   3 muestras de 16 segundos, empezando en A del mismo arreglo que después
   se escuchará completo, además de MIDI, partitura y análisis reutilizable.
2. **Escuchar completa** y **Elegir como favorita** son acciones independientes:
   el usuario puede comparar todas antes de elegir.
3. Para completar, Django crea otro job con `operacion: "completar"`,
   `versionElegida: 1/2/3` e `inputUrls: [GET firmado del analisis.json original]`.
   Solo se ejecutan arreglo y render de esa versión. No se vuelve a descargar
   el tarareo ni a ejecutar basic-pitch, tempo, tonalidad o armonización.
4. Django conserva las completas en R2 y su relación con el tarareo. Si se
   vuelve a pedir una terminada, entrega una URL GET nueva al objeto existente.
   Si sigue en proceso, sigue ese mismo job en vez de duplicarlo.

La operación por defecto sigue siendo `generar`: genera las versiones
completas como antes. Los nuevos campos son opcionales y están publicados
en `contratos/v1/solicitud_procesar.schema.json`.

## Archivos y tipos

| Archivo | Content-Type | Uso |
|---|---|---|
| `muestra.mp3`, `muestra-2.mp3`, `muestra-3.mp3` | `audio/mpeg` | Comparar estilos |
| `cancion.mp3`, `cancion-2.mp3`, `cancion-3.mp3` | `audio/mpeg` | Escuchar completas |
| `arreglo.mid`, `arreglo-2.mid`, `arreglo-3.mid` | `audio/midi` | Arreglo completo editable |
| `melodia.mid` | `audio/midi` | Idea melódica en tiempos |
| `partitura.musicxml` | `application/vnd.recordare.musicxml+xml` | Melodía y cifrado de acordes |
| `analisis.json` | `application/json` | Análisis para completar |

En la solicitud de muestras, firmar muestras/MIDI/partitura/JSON. Al completar,
firmar los nombres de la versión elegida y su JSON/partitura si se necesitan.
El worker solo utiliza URLs de archivos que produjo. Puede haber menos de
3 versiones si los otros estilos no encajan con el tarareo.

`analisis.json → versiones` y `metadatos.versiones` incorporan `tipo: "muestra"`
o `"completa"`. El JSON detallado también tiene la duración de la muestra y
la duración completa prevista. El JSON del hijo contiene solo esa versión;
conservar el análisis original para poder pedir las demás.

## Demo local y caché

- `POST /demo/completa/{origen}` con `{version: n}` responde 202 mientras
  se produce, o 200 con `cache: true` si ya existe.
- `GET /demo/completas/{origen}` informa el estado de todas las completas.
- Cada versión se identifica por tarareo, número y ajustes de sonido. Los
  clics repetidos siguen el mismo job. La caché usa archivos y sobrevive al
  reinicio del proceso, durante la retención local de 24 horas.
- Mientras se escucha una completa, el navegador puede pedir la siguiente
  con `anticipar: true`. Solo se admite sin otros jobs y con capacidad ≥ 2,
  reservando un cupo para peticiones explícitas. No se ponen las tres a
  renderizar en paralelo. Pausar evita anticipar otra más; un render ya
  iniciado termina y queda guardado.
- En producción la caché duradera la administra Django en R2; el worker
  no conoce la base de datos ni tiene credenciales de almacenamiento.

## Partitura y expresión

La partitura conserva alturas, acordes, silencios y tempo. Solo su **notación**
se redondea a semicorcheas para que se pueda imprimir; se abre en MuseScore
y desde ahí puede exportarse a PDF. No se instala un motor de PDF en el worker.

La expresión reutiliza los contornos de basic-pitch (tercios de semitono).
Se alinean con las notas limpias, se suavizan y se centran para no copiar el
desafinado constante. Se limitan a ±0.35 semitonos y se aplican a la melodía
en instrumentos sostenidos, con retorno neutro al terminar cada nota. No
se deslizan piano ni percusión. Se guarda en el análisis y pasa al MIDI con
pitch bends y rango explícito de 2 semitonos. Se puede desactivar con
`TARAREO_MELODIA_EXPRESIVA=false`.
