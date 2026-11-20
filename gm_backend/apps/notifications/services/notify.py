"""Punto de entrada: crea la notificación interna (idempotente por evento) y la entrega por push."""
from django.conf import settings

from apps.notifications.models import Notification
from apps.notifications.services.defaults import _DEFAULTS
from apps.notifications.services.delivery import _deliver_notification_delivery, _ensure_deliveries


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
