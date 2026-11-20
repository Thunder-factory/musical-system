import logging

from apps.notifications.firebase import send_push
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


_DEFAULTS = {
    'song_ready': ('Tu canción está lista', 'Ya puedes escucharla en tu biblioteca.'),
    'stem_ready': ('Pistas separadas listas', 'Descarga los stems desde la sección de separación.'),
    'faceswap_ready': ('Tu video está listo', 'Ya puedes verlo en Cambiar caras.'),
    'mix_ready': ('Mix exportado', 'Tu mezcla está lista para descargar.'),
    'karaoke_ready': ('Tu karaoke está listo', 'Ya puedes cantar con letra sincronizada.'),
    'translation_ready': ('Tu traducción está lista', 'Ya puedes ver tu video doblado.'),
    'humming_ready': ('Tu tarareo está listo', 'Ya puedes escuchar las versiones generadas.'),
    'credit_grant': ('Créditos agregados', 'Se agregaron créditos a tu cuenta.'),
    'system': ('Notificación', ''),
}


def notify_user(
    user,
    type: str,
    reference_id: str = None,
    title: str = None,
    message: str = None,
) -> None:
    """Crea una notificación interna y envía push FCM si hay token registrado."""
    default_title, default_msg = _DEFAULTS.get(type, ('Notificación', ''))
    notification_title = title or default_title
    notification_message = message or default_msg

    Notification.objects.create(
        user=user,
        type=type,
        title=notification_title,
        message=notification_message,
        reference_id=reference_id or '',
    )

    if not user.fcm_token:
        return

    try:
        send_push(
            token=user.fcm_token,
            title=notification_title,
            body=notification_message,
            data={
                'reference_id': reference_id or '',
                'type': type,
            },
        )
    except Exception:
        logger.exception(
            'No se pudo enviar la notificación push para el usuario %s.',
            user.id,
        )
