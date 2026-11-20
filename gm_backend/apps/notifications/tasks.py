from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import _DEFAULTS, notify_user


@shared_task
def retry_pending_push_notifications() -> int:
    """Reintenta entregas push fallidas sin duplicar la notificación interna."""
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return 0

    now = timezone.now()
    notification_ids = Notification.objects.filter(
        event_key__isnull=False,
        deliveries__status='pending',
        deliveries__next_attempt_at__isnull=False,
        deliveries__next_attempt_at__lte=now,
    ).filter(
        Q(deliveries__claimed_at__isnull=True)
        | Q(deliveries__claimed_at__lt=now - timedelta(minutes=5))
    ).values_list('id', flat=True).distinct()[:100]

    retried = 0
    for notification_id in notification_ids:
        notification = Notification.objects.filter(id=notification_id).select_related('user').first()
        if not notification:
            continue
        push_title, push_body = _DEFAULTS.get(notification.type, ('Notificación', ''))
        notify_user(
            notification.user,
            type=notification.type,
            reference_id=notification.reference_id,
            title=notification.title or push_title,
            message=notification.message,
            push_message=push_body,
            event_key=notification.event_key,
        )
        retried += 1
    return retried
