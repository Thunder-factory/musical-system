# Estribillo y variedad rítmica

El worker busca figuras de 3–8 notas con intervalos y ritmo parecidos en
dos lugares distintos del tarareo. Admite transposición y cierta variación
de duración. No considera repetir una sola altura como evidencia suficiente.
El gancho queda en `arreglo.gancho`, con origen, duración, confianza y motivo.

Si no encuentra repetición clara, elige una frase delimitada por pausas (o
una frase representativa corta) y la marca como **propuesta de composición**,
con `repetido=false` y confianza 0. No afirma haber detectado un estribillo.

La sección A conserva el tarareo completo como verso. A' utiliza el gancho
como estribillo y A final como estribillo final; B sigue siendo el puente.
Se conservan los identificadores internos A/A'/B para compatibilidad y se
añade `estructura[].funcion` para explicar su papel musical. El gancho se
repite con **sus propios acordes**, no sobre los de otra parte de la canción.
Mantiene también el vínculo con las curvas expresivas de las notas originales.
El número de secciones se sigue ajustando a la duración del arreglo.

Las muestras se toman del estribillo cuando existe, para que se compare el
gancho con el acompañamiento lleno; si no hay A', se toma el verso.

Cada estilo conserva sus tres variantes instrumentales y ahora ofrece tres
familias rítmicas, elegidas por la huella de la melodía:

- **Base:** patrones habituales del estilo.
- **Aire:** menos golpes de hi-hat o shaker y de bajo, acompañamiento más
  espaciado y dirección invertida en arpegios.
- **Impulso:** refuerzo de bombo, timbal o pandereta, bajo más corto y un
  golpe de acompañamiento a contratiempo cuando el patrón no lo tiene.

La batería mantiene la identidad del estilo: folk no recibe batería rock y
electrónico conserva el bombo en negras. Dentro de cada familia se mantiene
la distinción entre acompañamiento liviano y lleno por sección. La tabla
original no se modifica y el mismo tarareo conserva el mismo resultado.

Los ajustes se pueden comparar con `TARAREO_ARREGLO_CON_ESTRIBILLO=false` y
`TARAREO_ARREGLO_VARIEDAD_RITMICA=false`. Ambos están activos por defecto en
el pipeline. La caché de completas incorpora estos ajustes y una nueva
versión de identidad para no devolver canciones del arreglo anterior.
