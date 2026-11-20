from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import NotificationDelivery
from apps.notifications.services import _DEFAULTS, _deliver_notification_delivery, MAX_PUSH_ATTEMPTS


@shared_task
def retry_pending_push_notifications() -> int:
    """Reintenta entregas push fallidas sin duplicar la notificación interna."""
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return 0

    now = timezone.now()
    delivery_ids = NotificationDelivery.objects.filter(
        status='pending',
        attempts__lt=MAX_PUSH_ATTEMPTS,
    ).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now),
    ).filter(
        Q(claimed_at__isnull=True)
        | Q(claimed_at__lt=now - timedelta(minutes=5))
    ).values_list('id', flat=True)[:100]

    retried = 0
    for delivery_id in delivery_ids:
        delivery = NotificationDelivery.objects.select_related(
            'notification__user',
        ).filter(id=delivery_id).first()
        if not delivery:
            continue
        notification = delivery.notification
        push_title, push_body = _DEFAULTS.get(notification.type, ('Notificación', ''))
        _deliver_notification_delivery(
            delivery.id,
            title=notification.title or push_title,
            body=push_body,
            data={
                'reference_id': notification.reference_id or '',
                'type': notification.type,
                'title': notification.title or push_title,
                'body': push_body,
            },
        )
        retried += 1
    return retried
