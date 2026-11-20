# Evaluación de detectores de melodía

Compara basic-pitch (el actual) con CREPE, FCPE y pYIN usando tarareos sintéticos con notas conocidas (`sinteticos.py`) y los tarareos reales de `tests/audio`. Es solo una herramienta de medición: **nada de esto entra en la imagen del worker**.

Resultados y conclusiones: `../../docs/evaluacion-fase4.md`. Datos crudos: `resultados/detectores.json`.

## Correr

Con la imagen del worker (trae basic-pitch ONNX, librosa y mir_eval), desde la carpeta `gm_tarareo`:

```bash
docker run --rm -it -u 0 -w /app \
  -v "$PWD/evaluacion:/app/evaluacion" -v "$PWD/tests:/app/tests:ro" \
  --entrypoint sh worker-tarareo:dev -c "
    pip install torch --index-url https://download.pytorch.org/whl/cpu &&
    pip install -r evaluacion/requirements-evaluacion.txt &&
    python -m evaluacion.comparar_detectores --sinteticos 40 --salida evaluacion/resultados"
```

Tarda unos 15-20 minutos en CPU; casi todo el tiempo se va en CREPE.
