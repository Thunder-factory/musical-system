from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class TranslationJob(BaseModel):
    """Doblaje de un video musical a otro idioma conservando la voz del cantante."""

    STATUS_CHOICES = [
        ('queued', 'En cola'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Error'),
    ]
    LANGUAGE_CHOICES = [
        ('en', 'Inglés'),
        ('es', 'Español'),
        ('fr', 'Francés'),
        ('zh', 'Chino'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='translation_jobs',
    )

    # Video original subido por el usuario (clave privada en R2).
    source_video_key = models.TextField(blank=True, default='')
    source_filename = models.CharField(max_length=255)
    source_file_size_bytes = models.BigIntegerField()
    source_sha256 = models.CharField(max_length=64, null=True, blank=True)
    source_duration_seconds = models.FloatField(null=True, blank=True)

    # Parámetros del doblaje.
    target_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    song_title = models.CharField(max_length=200, blank=True, default='')
    song_artist = models.CharField(max_length=200, blank=True, default='')

    # Seguimiento del trabajo remoto en Modal.
    remote_job_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    mode = models.CharField(max_length=20, blank=True, default='')  # simulated | real
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    stage = models.CharField(max_length=30, blank=True, default='en_cola')
    progress_pct = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    credits_used = models.IntegerField(default=0)

    # Resultados (claves privadas en R2 y letra para mostrar en la web).
    result_video_key = models.TextField(blank=True, default='')
    result_audio_key = models.TextField(blank=True, default='')
    result_lyrics_key = models.TextField(blank=True, default='')
    lyrics = models.JSONField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'source_sha256', 'target_language'],
                condition=models.Q(status__in=['queued', 'processing']),
                name='unique_active_translation_source',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.source_filename} → {self.target_language} ({self.status})'
