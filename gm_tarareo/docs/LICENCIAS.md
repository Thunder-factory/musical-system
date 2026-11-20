# Licencias de terceros (restricción 7: uso comercial)

Registro de modelos, binarios y recursos que usa el worker, con la licencia
verificada y de dónde salió cada uno. Antes de agregar algo nuevo, se anota
acá con la misma información.

| Recurso | Uso | Licencia | Origen y verificación |
|---|---|---|---|
| **basic-pitch 0.4.0** (Spotify) | Etapa 3: audio → notas | Apache 2.0 | PyPI (`requirements.txt`) |
| **FluidSynth 2.6.2** | Etapa 8: MIDI → audio | LGPL-2.1 (se usa como programa externo, sin enlazarlo) | Release oficial `FluidSynth/fluidsynth` en GitHub, `fluidsynth-v2.6.2-win10-x64-cpp11.zip`, SHA-256 `808295345d43c9c428f3fa87d29fbf97a9926f356df95559ff2689f3bd4072d7` (coincide con el publicado). En Docker: paquete Debian `fluidsynth` |
| **FluidR3_GM.sf2** (Frank Wen) | Etapa 8: sonidos General MIDI | **MIT** | Paquete Debian estable (trixie) `fluid-soundfont-gm_3.1-5.3_all.deb`, SHA-256 `6f531493ac4e4d9772fd96b2488ea1790af81c196135fbdd25997da0781fc60e` (coincide con el índice de Debian). Texto de la licencia: `herramientas/soundfonts/FluidR3_GM-LICENCIA.txt`. La GPL del paquete cubre solo los scripts de empaquetado de Debian, no el SoundFont |
| **ffmpeg** | Ingesta, loudness, MP3 (`libmp3lame`) | LGPL/GPL según el build | Programa externo del sistema |

Verificado el 2026-11-14.

**Descartados por licencia:** MusicGen, YuE2 y YuE2-Studio (pesos CC BY-NC,
no comercial). **GeneralUser GS** (SoundFont): su licencia v2.0 permite uso
comercial, pero el autor no puede garantizar el origen de todas las muestras
y el banco "hereda" sus derechos; Debian lo considera no libre. Ver `CLAUDE.md`.

**Instalado para comparar:** `MuseScore_General_Full.sf3` 0.2.1 (S. Christian
Collins, deriva de FluidR3): **MIT**, con partes en dominio público o CC0
(piano Splendid Grand, cuerdas VSCO, percusión MDL/VCSL). Paquete Debian
estable `musescore-general-soundfont_0.2.1-1_all.deb`, SHA-256
`21ab87e4b15711817f84130a370bdb51003c90f3bf53e4015f3b410b9ed8c6a5` (coincide
con el índice de Debian). Licencia y origen de cada muestra en
`herramientas/soundfonts/MuseScore_General-LICENCIA.txt` y
`MuseScore_General-ORIGEN_MUESTRAS.csv`. Formato `.sf3` (comprimido): el
render tarda ~16 s en vez de ~1.3 s porque descomprime las muestras al cargar.

## Dónde viven los binarios

FluidSynth y el SoundFont **no van en el repositorio** (binario y ~140 MB).
En desarrollo local están en `herramientas/` (ignorado por git):

```
herramientas/
├─ fluidsynth/fluidsynth-v2.6.2-win10-x64-cpp11/bin/fluidsynth.exe
└─ soundfonts/FluidR3_GM.sf2  (+ FluidR3_GM-LICENCIA.txt)
```

En Docker se instalan con `apt-get install fluidsynth fluid-soundfont-gm` y se
configuran con `TARAREO_FLUIDSYNTH` y `TARAREO_SOUNDFONT`.
