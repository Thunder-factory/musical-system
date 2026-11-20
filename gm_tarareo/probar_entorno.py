"""
Prueba de humo del worker de tarareo.

Genera una melodia sintetica (do-re-mi-fa-sol), la pasa por basic-pitch
y verifica que la IA devuelva exactamente esas notas.

Si esto funciona, todo el stack de audio esta bien instalado.

Uso:
    (venv) python probar_entorno.py
    (venv) python probar_entorno.py mi_tarareo.wav     <- con tu propio audio
"""

import logging
import os
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")  # callar el ruido de TensorFlow
logging.getLogger().setLevel(logging.ERROR)         # y el de basic-pitch

ARCHIVO_PRUEBA = "melodia_prueba.wav"

# do re mi fa sol  (C4 D4 E4 F4 G4)
FRECUENCIAS = [(261.63, 0.5), (293.66, 0.5), (329.63, 0.5),
               (349.23, 0.5), (392.00, 1.0)]
ESPERADAS = ["C4", "D4", "E4", "F4", "G4"]


def verificar_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("XX  ffmpeg no esta en el PATH. Instalalo antes de seguir.")
        return False


def generar_melodia(destino: str) -> None:
    """Arma un WAV con las cinco notas usando ffmpeg."""
    entradas, etiquetas = [], ""
    for i, (freq, dur) in enumerate(FRECUENCIAS):
        entradas += ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}"]
        etiquetas += f"[{i}]"

    subprocess.run(
        ["ffmpeg", "-loglevel", "error", *entradas,
         "-filter_complex", f"{etiquetas}concat=n={len(FRECUENCIAS)}:v=0:a=1",
         "-ar", "22050", "-ac", "1", destino, "-y"],
        check=True,
    )


def main() -> int:
    print("=" * 58)
    print("  PRUEBA DE ENTORNO - Worker de Tarareo")
    print("=" * 58)

    print(f"\nPython: {sys.version.split()[0]}")
    if sys.version_info[:2] != (3, 11):
        print("  !!  Se esperaba Python 3.11. basic-pitch no soporta 3.12+.")

    # --- imports ------------------------------------------------------
    print("\n1) Librerias")
    faltantes = []
    for nombre in ["numpy", "scipy", "librosa", "soundfile", "basic_pitch",
                   "pretty_midi", "music21", "fastapi"]:
        try:
            mod = __import__(nombre)
            print(f"   OK  {nombre:<14} {getattr(mod, '__version__', 'instalado')}")
        except ImportError as e:
            print(f"   XX  {nombre:<14} {e}")
            faltantes.append(nombre)

    if faltantes:
        print(f"\nFaltan: {', '.join(faltantes)}")
        print("Corre:  pip install -r requirements.txt")
        return 1

    import numpy
    if int(numpy.__version__.split(".")[0]) >= 2:
        print(f"\n   !!  numpy {numpy.__version__} — basic-pitch necesita 1.x")
        print("       pip install 'numpy<2.0'")
        return 1

    # --- ffmpeg -------------------------------------------------------
    print("\n2) ffmpeg")
    if not verificar_ffmpeg():
        return 1
    print("   OK  disponible en el PATH")

    # --- audio de prueba ----------------------------------------------
    audio = sys.argv[1] if len(sys.argv) > 1 else ARCHIVO_PRUEBA
    propio = len(sys.argv) > 1

    print("\n3) Audio de entrada")
    if propio:
        if not os.path.exists(audio):
            print(f"   XX  no existe: {audio}")
            return 1
        print(f"   OK  usando tu archivo: {audio}")
    else:
        generar_melodia(audio)
        print(f"   OK  melodia sintetica generada: {audio}")

    # --- la IA --------------------------------------------------------
    print("\n4) Extraccion de melodia (basic-pitch)")
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
    import pretty_midi

    _, midi, notas = predict(audio, ICASSP_2022_MODEL_PATH)
    notas = sorted(notas, key=lambda n: n[0])

    print(f"   Notas detectadas: {len(notas)}\n")
    detectadas = []
    for inicio, fin, pitch, amp, _ in notas:
        nombre = pretty_midi.note_number_to_name(pitch)
        detectadas.append(nombre)
        print(f"     {nombre:>4} ({pitch:3d})  "
              f"{inicio:5.2f}s -> {fin:5.2f}s   amp={amp:.2f}")

    salida_midi = os.path.splitext(audio)[0] + ".mid"
    midi.write(salida_midi)
    print(f"\n   MIDI generado: {salida_midi}")

    # --- tempo y tonalidad ---------------------------------------------
    print("\n5) Analisis musical (librosa)")
    import librosa
    y, sr = librosa.load(audio, sr=22050)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(tempo) if hasattr(tempo, "__len__") is False else float(tempo[0])
    print(f"   BPM estimado: {tempo:.1f}")
    print(f"   Duracion:     {len(y)/sr:.2f}s")

    # --- veredicto -----------------------------------------------------
    print("\n" + "=" * 58)
    if propio:
        print("  Pipeline ejecutado. Revisa arriba si las notas tienen sentido.")
        return 0

    if detectadas == ESPERADAS:
        print("  TODO OK - la IA detecto do-re-mi-fa-sol correctamente.")
        print("  El entorno esta listo para construir el worker.")
        return 0

    print(f"  Se esperaba {ESPERADAS}")
    print(f"  Se detecto  {detectadas}")
    print("  El stack funciona, pero revisa la configuracion de audio.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
