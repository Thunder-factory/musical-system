import logging
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.notifications.firebase import send_push
from apps.notifications.models import Notification, NotificationDelivery
from apps.users.models import UserDevice

logger = logging.getLogger(__name__)
MAX_PUSH_ATTEMPTS = 5


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
            send_push(token=token, title=title, body=body, data=data or {})
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


def _ensure_deliveries(notification: Notification, user) -> list[int]:
    delivery_ids = []
    for token in _user_push_tokens(user):
        delivery, _ = NotificationDelivery.objects.get_or_create(
            notification=notification,
            token=token,
        )
        delivery_ids.append(delivery.id)
    return delivery_ids


def _claim_delivery(delivery_id: int) -> bool:
    now = timezone.now()
    with transaction.atomic():
        delivery = NotificationDelivery.objects.select_for_update().get(id=delivery_id)
        if delivery.status != 'pending' or delivery.attempts >= MAX_PUSH_ATTEMPTS:
            return False
        if delivery.claimed_at and delivery.claimed_at > now - timedelta(minutes=5):
            return False
        delivery.claimed_at = now
        delivery.attempts += 1
        delivery.save(update_fields=['claimed_at', 'attempts'])
        Notification.objects.filter(id=delivery.notification_id).update(
            push_attempts=models.F('push_attempts') + 1,
        )
        return True


def _update_notification_delivery_state(notification_id: int) -> None:
    pending = NotificationDelivery.objects.filter(
        notification_id=notification_id,
        status='pending',
    )
    if not pending.exists():
        permanent_failure = NotificationDelivery.objects.filter(
            notification_id=notification_id,
            status='permanent_failure',
        ).exists()
        Notification.objects.filter(id=notification_id).update(
            push_sent_at=None if permanent_failure else timezone.now(),
            push_claimed_at=None,
            push_next_attempt_at=None,
            push_last_error=(
                NotificationDelivery.objects.filter(
                    notification_id=notification_id,
                    status='permanent_failure',
                ).exclude(last_error='').values_list('last_error', flat=True).first() or ''
            ),
        )
        return
    next_attempt = pending.exclude(next_attempt_at__isnull=True).order_by('next_attempt_at').values_list(
        'next_attempt_at', flat=True,
    ).first()
    last_error = pending.exclude(last_error='').values_list('last_error', flat=True).first() or ''
    Notification.objects.filter(id=notification_id).update(
        push_sent_at=None,
        push_claimed_at=None,
        push_next_attempt_at=next_attempt,
        push_last_error=last_error,
    )


def _deliver_notification_delivery(delivery_id: int, *, title: str, body: str, data: dict) -> None:
    if not _claim_delivery(delivery_id):
        return
    delivery = NotificationDelivery.objects.select_related('notification__user').get(id=delivery_id)
    sent = False
    error = ''
    permanent = False
    try:
        send_push(token=delivery.token, title=title, body=body, data=data)
        sent = True
    except Exception as exc:
        error = str(exc)[:1000]
        permanent = _is_invalid_fcm_token_error(exc)
        if permanent:
            _deactivate_token(delivery.notification.user, delivery.token)
        logger.exception('No se pudo enviar la notificación push %s.', delivery.notification_id)

    now = timezone.now()
    if sent:
        NotificationDelivery.objects.filter(id=delivery_id).update(
            status='sent', sent_at=now, claimed_at=None, last_error='', next_attempt_at=None,
        )
    elif permanent or delivery.attempts >= MAX_PUSH_ATTEMPTS:
        NotificationDelivery.objects.filter(id=delivery_id).update(
            status='permanent_failure', claimed_at=None, last_error=error, next_attempt_at=None,
        )
    else:
        NotificationDelivery.objects.filter(id=delivery_id).update(
            claimed_at=None,
            last_error=error,
            next_attempt_at=now + timedelta(seconds=min(3600, 60 * (2 ** delivery.attempts))),
        )
    _update_notification_delivery_state(delivery.notification_id)


def notify_user(
    user,
    type: str,
    reference_id: str = None,
    title: str = None,
    message: str = None,
    push_message: str = None,
    event_key: str = None,
) -> None:
    """Crea la notificación interna y envía un push resumido cuando corresponde."""
    default_title, default_msg = _DEFAULTS.get(type, ('Notificación', ''))
    notification_title = title or default_title
    notification_message = message or default_msg

    resolved_event_key = event_key or (
        f'{type}:{reference_id}' if reference_id else None
    )
    defaults = {
        'type': type,
        'title': notification_title,
        'message': notification_message,
        'reference_id': reference_id or '',
    }
    if resolved_event_key:
        notification, created = Notification.objects.get_or_create(
            user=user,
            event_key=resolved_event_key,
            defaults=defaults,
        )
    else:
        notification = Notification.objects.create(
            user=user,
            event_key=None,
            **defaults,
        )
        created = True

    # Un mismo evento no crea otra fila. Si el primer push falló, se permite
    # reintentarlo, pero con un lease para no duplicarlo concurrentemente.
    if not created and notification.push_sent_at:
        return

    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return
    delivery_ids = _ensure_deliveries(notification, user)
    data = {
        'reference_id': reference_id or '',
        'type': type,
        'title': notification_title,
        'body': push_message or notification_message,
    }
    for delivery_id in delivery_ids:
        _deliver_notification_delivery(
            delivery_id,
            title=notification_title,
            body=push_message or notification_message,
            data=data,
        )
