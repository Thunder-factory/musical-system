"""Títulos y mensajes por defecto de cada tipo de notificación."""

_DEFAULTS = {
    'song_ready': ('Tu canción está lista', 'Ya puedes escucharla en tu biblioteca.'),
    'song_failed': ('No se pudo generar la canción', 'La generación de tu canción no pudo completarse.'),
    'karaoke_ready': ('Tu Karaoke está listo', 'Ya puedes cantar con tu pista.'),
    'karaoke_failed': ('No se pudo generar el Karaoke', 'El procesamiento del Karaoke no pudo completarse.'),
    'stem_ready': ('Pistas separadas listas', 'Descarga los stems desde la sección de separación.'),
    'stem_failed': ('No se pudieron separar las pistas', 'La separación de pistas no pudo completarse.'),
    'humming_ready': ('Tu tarareo está listo', 'Ya puedes revisar el resultado de tu tarareo.'),
    'humming_failed': ('No se pudo procesar el tarareo', 'El procesamiento del tarareo no pudo completarse.'),
    'translation_ready': ('Traducción lista', 'Tu traducción ya está disponible.'),
    'translation_failed': ('No se pudo completar la traducción', 'La traducción no pudo completarse.'),
    'faceswap_ready': ('Tu video está listo', 'Ya puedes verlo en Cambiar caras.'),
    'faceswap_failed': ('No se pudo procesar el video', 'El procesamiento del video no pudo completarse.'),
    'mix_ready': ('Mix exportado', 'Tu mezcla está lista para descargar.'),
    'mix_failed': ('No se pudo exportar el mix', 'La exportación del mix no pudo completarse.'),
    'credit_grant': ('Créditos agregados', 'Se agregaron créditos a tu cuenta.'),
    'credit_low': ('Créditos bajos', 'Quedan pocos créditos disponibles en tu cuenta.'),
    'system': ('Notificación', ''),
}
