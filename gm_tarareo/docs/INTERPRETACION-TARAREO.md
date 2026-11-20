# Interpretación más fiel del tarareo

## Problemas observados en el diseño anterior

La limpieza eliminaba cualquier nota a más de una octava de la mediana y
cualquier evento con amplitud del modelo menor de 0.40. Esas reglas ayudaban
en el lote inicial, pero también podían eliminar un salto real o una nota
clara de otro timbre. No había otra medición acústica para contrastarlas.

En ritmo libre, cada distancia entre notas se redondeaba por separado y se
sumaba a la anterior. Los pequeños errores se podían acumular: una frase
terminaba adelantada o atrasada respecto de lo que se cantó. Además una nota
larga podía interpretarse como pausa a partir de la distancia entre ataques.

La expresión reproducía oscilaciones de hasta 35 cents en instrumentos
sostenidos. Aunque se eliminaba la desviación constante, podía seguir sonando
inestable.

## Cambios

`pipeline/interpretacion.py` ejecuta YIN de librosa como segunda opinión
monofónica, con filtro de energía, periodicidad y estabilidad. Usa la señal
de cada grabación; no consulta canciones ni selecciona una melodía de ejemplo.

- Estima una referencia de afinación propia a partir de al menos cuatro
  mediciones consistentes. La referencia está limitada a ±45 cents; no puede
  deducir qué nota quiso cantar alguien ante una ambigüedad grande.
- Corrige desacuerdos de hasta un semitono únicamente con altura estable y
  energía espectral en la fundamental. No transpone octavas por decisión de
  YIN: también puede equivocarse por una octava. Los duplicados se siguen
  resolviendo en limpieza.
- Preserva saltos fuera del rango original y eventos de amplitud 0.20–0.40
  cuando la señal los corrobora. Se conserva la duración mínima de 80 ms.
- Si la confianza media del modelo está entre 0.20 y el umbral habitual,
  puede aceptar la entrada si se corroboran al menos cuatro notas y el 70 %
  de los eventos. El ruido y la ausencia de tono siguen siendo rechazos.
- No fuerza las notas a una escala mayor o menor. Los cromatismos respaldados
  por el audio permanecen.

El resultado se registra en `analisis.json` → `interpretacion`: referencia en
cents, cantidad de notas verificadas, ajustes original/corregida y motivo.
El campo es opcional para leer análisis antiguos.

`regularizar_fiel` ajusta posiciones absolutas con un movimiento máximo de
0.10 pulsos, compara semicorcheas y tresillos y conserva lo que queda lejos
de la grilla. Comprime silencios largos efectivos, no notas largas. El tempo
libre continúa siendo una propuesta del sistema; no se afirma haber detectado
un pulso que no existe. El arreglo sigue en 4/4: admitir tresillos no equivale
a inferir automáticamente todos los compases.

La intensidad expresiva del pipeline pasa al 40 %: como máximo 14 cents en
los contornos nuevos, conservando el gesto. Los modelos de datos siguen
admitiendo curvas antiguas de 35 cents.

## Configuración

```dotenv
TARAREO_INTERPRETACION_VERIFICAR_ALTURAS=true
TARAREO_ANALISIS_RITMO_FIEL=true
TARAREO_EXPRESION_INTENSIDAD=0.4
```

Sin nuevas dependencias, entrenamiento o GPU. El calentamiento incluye YIN
para que la compilación inicial no recaiga sobre el primer usuario. Las
completas usan caché v5. Para comparar muestras y completas del sistema nuevo,
hay que generar un análisis nuevo; completar desde un análisis antiguo conserva
sus notas y expresión guardadas.

## Alcance y validación

No hay una lista cerrada de tarareos aceptados. Los audios iniciales sirven
para regresiones, no son una biblioteca de canciones. Siguen existiendo límites
de entrada: sonido tonal con notas distinguibles, duración útil y calidad mínima.
Esto no permite garantizar la interpretación de cualquier ruido, varias voces
superpuestas o una intención musical que no sea audible.

`tests/test_interpretacion.py` usa ideas sintéticas nuevas, registros desde MIDI
36 hasta 98, armónicos y ruido, desviaciones de ±38 cents, cromatismos, saltos
amplios, notas de baja confianza, tresillos, notas sostenidas y pausas. También
verifica que no se acumule el error temporal. Los umbrales acústicos son
conservadores y requieren validación auditiva con más voces reales.

Validación del 2026-11-15: suite completa de 400 tests en Docker/ONNX y 24
casos nuevos de interpretación en Windows. También se ejecutaron 192 pruebas
relacionadas durante la primera ronda. Se generó una comparación A/B de las tres
grabaciones recientes: una dio melodía (34 eventos corroborados, sin cambios
de altura); en dos no se corroboraron suficientes notas y se mantuvo el rechazo.
La mejora de ritmo y la reducción de expresión necesitan confirmación auditiva
del usuario; pasar tests no demuestra una mejora perceptual universal.

Demo actualizada en `http://localhost:8004/demo`: verificación HTTP de muestras,
completas y caché correcta. Tres muestras en 9.71 s; dos completas en 8.12 y
7.08 s, caché en 10 ms, con MIDI idéntico entre muestra y completa. Estos tiempos
corresponden a esta máquina y a un tarareo de prueba.
