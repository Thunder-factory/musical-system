"""
Lógica de edición de audio para el mix.
Usa pydub para cortes, fades y mezcla.
Requiere ffmpeg instalado en el sistema.
"""
from pydub import AudioSegment
import pydub
from decouple import config
import tempfile
import os

from ml.storage_client import download_fileobj

ffmpeg_path = config('FFMPEG_PATH', default=None)
if ffmpeg_path:
    pydub.AudioSegment.converter = ffmpeg_path


def download_audio_from_storage(object_key: str) -> str:
    """Descarga un objeto de R2 a un archivo temporal."""
    suffix = '.wav' if object_key.endswith('.wav') else '.mp3'
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    download_fileobj(object_key, tmp)
    tmp.close()
    return tmp.name


def apply_clip_effects(audio: AudioSegment, clip) -> AudioSegment:
    """
    Aplica corte, fade in, fade out y volumen a un segmento de audio.
    Implementa HU-43 (corte) y HU-44 (fades).
    """
    # HU-43: cortar el fragmento exacto que pidió el usuario
    segment = audio[clip.start_time_ms:clip.end_time_ms]

    # HU-44: aplicar fades suaves en los bordes
    if clip.fade_in_ms > 0:
        segment = segment.fade_in(clip.fade_in_ms)
    if clip.fade_out_ms > 0:
        segment = segment.fade_out(clip.fade_out_ms)

    # Ajustar volumen: 1.0 = sin cambio, 0.5 ≈ -6dB, 2.0 ≈ +6dB
    if clip.volume != 1.0:
        db_change = 20 * (clip.volume - 1.0)
        segment = segment + db_change

    return segment


def get_clip_storage_key(clip) -> str:
    """Obtiene la clave de almacenamiento de la fuente del clip."""
    if clip.song and clip.song.audio_s3_key:
        return clip.song.audio_s3_key
    elif clip.stem_file and clip.stem_file.audio_s3_key:
        return clip.stem_file.audio_s3_key
    elif clip.custom_audio_s3_key:
        return clip.custom_audio_s3_key
    raise ValueError(f"Clip {clip.id} no tiene fuente de audio válida.")
