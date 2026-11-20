"""Entregas push por dispositivo: lease, reintentos con backoff y estado agregado."""
import logging
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

from apps.notifications import services as pkg
from apps.notifications.models import Notification, NotificationDelivery
from apps.notifications.services.push import _deactivate_token, _is_invalid_fcm_token_error, _user_push_tokens
from apps.users.models import UserDevice

logger = logging.getLogger(__name__)
MAX_PUSH_ATTEMPTS = 5


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
        if delivery.next_attempt_at and delivery.next_attempt_at > now:
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
    token_is_owned = UserDevice.objects.filter(
        user=delivery.notification.user,
        token=delivery.token,
        is_active=True,
    ).exists()
    if not token_is_owned:
        NotificationDelivery.objects.filter(id=delivery_id).update(
            status='permanent_failure',
            claimed_at=None,
            next_attempt_at=None,
            last_error='El token ya no pertenece al usuario de la notificación.',
        )
        _update_notification_delivery_state(delivery.notification_id)
        return
    sent = False
    error = ''
    permanent = False
    try:
        pkg.send_push(token=delivery.token, title=title, body=body, data=data)
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
