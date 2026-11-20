"""Tokens de dispositivos y envío push directo (FCM)."""
import logging

from django.conf import settings

from apps.notifications import services as pkg
from apps.users.models import UserDevice

logger = logging.getLogger(__name__)


def _user_push_tokens(user) -> set[str]:
    tokens = set(
        UserDevice.objects.filter(user=user, is_active=True)
        .exclude(token='')
        .values_list('token', flat=True)
    )
    # Compatibilidad durante la transición desde User.fcm_token.
    if user.fcm_token:
        tokens.add(user.fcm_token)
    return tokens


def _is_invalid_fcm_token_error(exc: Exception) -> bool:
    code = str(getattr(exc, 'code', '') or '').lower()
    detail = str(exc).lower()
    return code in {
        'messaging/registration-token-not-registered',
        'messaging/invalid-registration-token',
        'registration-token-not-registered',
        'invalid-registration-token',
    } or 'registration token is not registered' in detail


def _deactivate_token(user, token: str) -> None:
    UserDevice.objects.filter(user=user, token=token).update(is_active=False)
    if user.fcm_token == token:
        user.fcm_token = None
        user.save(update_fields=['fcm_token'])


def send_push_to_user(user, *, title: str, body: str, data: dict | None = None) -> tuple[bool, str]:
    """Envía un push a todos los dispositivos activos y desactiva tokens inválidos."""
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return False, ''
    sent = False
    last_error = ''
    for token in _user_push_tokens(user):
        try:
            pkg.send_push(token=token, title=title, body=body, data=data or {})
            sent = True
        except Exception as exc:
            last_error = str(exc)[:1000]
            if _is_invalid_fcm_token_error(exc):
                _deactivate_token(user, token)
            logger.exception(
                'No se pudo enviar la notificación push al usuario %s.',
                user.id,
            )
    return sent, last_error
