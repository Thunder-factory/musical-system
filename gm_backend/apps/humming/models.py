from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class HummingJob(BaseModel):
    """
    Un tarareo enviado al worker gm_tarareo.

    status: queued → processing → completed | failed

    El worker nunca toca la base: Django firma las URLs de R2 al despachar,
    el worker sube las salidas y avisa por callback (con polling de respaldo).
    Cuando el usuario elige una versión, se crea una Song con source_type='hummed'.
    """

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    TERMINAL_STATUSES = frozenset({'completed', 'failed'})

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='humming_jobs',
    )
    title = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    progress = models.PositiveSmallIntegerField(default=0)
    stage = models.CharField(max_length=60, blank=True, default='')

    input_s3_key = models.TextField()
    # Nombre de salida del worker (p. ej. "cancion-2.mp3") → clave en R2.
    output_keys = models.JSONField(default=dict, blank=True)
    # Nombres de salida que el worker ya confirmó haber subido.
    available_outputs = models.JSONField(default=list, blank=True)
    # metadatos del worker: bpm, tonalidad, acordes, estilo, versiones...
    metadata = models.JSONField(null=True, blank=True)

    error_message = models.TextField(null=True, blank=True)
    # ENTRADA_INVALIDA (definitivo) | ERROR_INTERNO (reintentable) | código propio de Django
    error_code = models.CharField(max_length=40, blank=True, default='')

    credits_used = models.IntegerField(default=0)
    dispatch_attempts = models.PositiveSmallIntegerField(default=0)

    chosen_version = models.PositiveSmallIntegerField(null=True, blank=True)
    song = models.OneToOneField(
        'songs.Song',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='humming_job',
    )

    started_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f'HummingJob {self.id} ({self.status})'

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL_STATUSES

    @property
    def versions(self) -> list[dict]:
        return list((self.metadata or {}).get('versiones') or [])
