# Acabado ligero de la canción (etapa 8)

Activo por defecto con `TARAREO_RENDER_MASTERIZACION=true`. Para comparar
con el sonido anterior, usar `false` y volver a generar el audio. Se aplica
a la canción principal y a sus alternativas, tanto en local como en Docker.
No añade dependencias ni requiere GPU.

## Procesamiento

1. **Ambiente en FluidSynth:** reverb activa, nivel 0.18, tamaño de sala
   0.30 y amortiguación 0.55. FluidSynth ya trae reverb: se modera esa misma
   para no tapar la melodía, sin sumar otro eco a toda la mezcla.
2. **Ecualización en ffmpeg:** paso alto a 30 Hz, corte ancho de -1.2 dB
   alrededor de 280 Hz y realce ancho de +0.6 dB alrededor de 2800 Hz.
3. **Compresión suave:** umbral -30 dBFS sobre el render previo a normalizar,
   relación 1.3:1, ataque de 30 ms, recuperación de 200 ms y rodilla suave.
   Los dos canales comparten la reducción para conservar el panorama. No
   tiene ganancia automática.
4. **Volumen final:** se mantiene la medición `ebur128`, la ganancia al
   objetivo configurado (-16 LUFS), el limitador de seguridad y el MP3 a
   192 kbps. El mismo procesamiento de EQ/compresión precede tanto a la
   medición como a la codificación; así el cálculo de ganancia sigue siendo
   válido. El fade-out se aplica después de la compresión.

La configuración está en `app/pipeline/masterizacion.py`. Para registrar
cómo se produjo cada canción, `analisis.json → render.masterizacion` indica
`suave-v1` o `desactivada`. Los indicadores de loudness del render se miden
antes del codificador MP3; las pruebas también miden el archivo decodificado,
porque una compresión con pérdidas puede cambiar ligeramente sus picos.

## Comparación de oído

Las versiones de comparación están en `salidas/masterizacion/`: el mismo
MIDI, SoundFont y objetivo de volumen, con y sin acabado. Los nombres acaban
en `-antes.mp3` y `-masterizada.mp3`. El informe de las mediciones sobre los
MP3 finales se guarda en `informe.json` dentro de esa carpeta (ignorada por Git).

La validación automática comprueba la reducción de subgraves, la compresión
moderada, la conservación del estéreo, la duración, el volumen y los picos.
La preferencia sonora se confirma escuchando: esos valores no garantizan
por sí solos que una mezcla guste más.

Validación del 2026-11-14: 49 pruebas relacionadas pasan en Windows (render,
procesamiento de señal, núcleo, demo, contrato y subida a R2 simulada) y 16
de render/procesamiento de señal/contrato dentro de Docker con ONNX. Los 9
MIDIs del lote se renderizaron con el perfil nuevo: los MP3 decodificados
dan entre -16.2 y -16.3 LUFS y picos entre -1.5 y -3.9 dBTP, sin cambio de
duración relevante (máximo 1 ms). No se repitió la suite completa.
