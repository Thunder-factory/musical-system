from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_CHOICES = [
        ('song_ready',   'Canción lista'),
        ('song_failed',  'Canción fallida'),
        ('karaoke_ready', 'Karaoke listo'),
        ('karaoke_failed', 'Karaoke fallido'),
        ('stem_ready',   'Stems listos'),
        ('stem_failed',  'Separación fallida'),
        ('humming_ready', 'Tarareo mejorado'),
        ('humming_failed', 'Tarareo fallido'),
        ('translation_ready', 'Traducción lista'),
        ('translation_failed', 'Traducción fallida'),
        ('mix_ready',    'Mix exportado'),
        ('mix_failed',   'Mix fallido'),
        ('faceswap_ready', 'Face swap listo'),
        ('faceswap_failed', 'Face swap fallido'),
        ('credit_grant', 'Créditos otorgados'),
        ('credit_low',   'Créditos bajos'),
        ('system',       'Sistema'),
    ]

    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type         = models.CharField(max_length=30, choices=TYPE_CHOICES, default='system')
    title        = models.CharField(max_length=200)
    message      = models.TextField(blank=True, default='')
    reference_id = models.CharField(max_length=100, blank=True, default='')
    event_key    = models.CharField(max_length=255, null=True, blank=True, default=None)
    is_read      = models.BooleanField(default=False)
    push_attempts = models.PositiveIntegerField(default=0)
    push_claimed_at = models.DateTimeField(null=True, blank=True, default=None)
    push_sent_at = models.DateTimeField(null=True, blank=True, default=None)
    push_next_attempt_at = models.DateTimeField(null=True, blank=True, default=None)
    push_last_error = models.TextField(blank=True, default='')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'event_key'],
                condition=models.Q(event_key__isnull=False),
                name='unique_notification_event_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.type} → {self.user.email}"


class NotificationDelivery(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviada'),
        ('permanent_failure', 'Fallida permanentemente'),
    ]

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='deliveries',
    )
    token = models.TextField()
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    claimed_at = models.DateTimeField(null=True, blank=True, default=None)
    next_attempt_at = models.DateTimeField(null=True, blank=True, default=None)
    sent_at = models.DateTimeField(null=True, blank=True, default=None)
    last_error = models.TextField(blank=True, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['notification', 'token'],
                name='unique_notification_delivery_token',
            ),
        ]
