from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class FaceSwapTemplate(BaseModel):
    """
    Video base del catálogo que el admin ofrece para cambiar caras.

    Borrado lógico: deleted_at + is_active=False. Nunca se borra la fila ni sus
    objetos en R2 porque los jobs la referencian con PROTECT.
    """

    title = models.CharField(max_length=120)
    video_s3_key = models.TextField()
    thumbnail_s3_key = models.TextField()
    duration_seconds = models.FloatField()
    # Segundo donde se ve sola la cara a reemplazar; null = "cara más grande".
    ref_time_s = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(ref_time_s__isnull=True) | models.Q(ref_time_s__gte=0),
                name='faceswap_template_ref_time_non_negative',
            ),
        ]

    def __str__(self):
        return self.title


class FaceSwapJob(BaseModel):
    """
    Job de cambio de cara sobre un video corto (plantilla o clip propio).

    Máquina de estados: queued → processing → completed | failed.
    Un usuario solo puede tener un job activo (constraint parcial).
    """

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    SOURCE_CHOICES = [
        ('template', 'Template'),
        ('upload', 'Upload'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='faceswap_jobs',
    )
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    template = models.ForeignKey(
        FaceSwapTemplate,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='jobs',
    )
    photo_s3_key = models.TextField(null=True, blank=True)
    source_video_s3_key = models.TextField(null=True, blank=True)
    source_video_filename = models.CharField(max_length=255, blank=True, default='')
    source_duration_seconds = models.FloatField(null=True, blank=True)
    ref_time_s = models.FloatField(null=True, blank=True)
    # Clic del usuario sobre la cara a reemplazar, normalizado (0..1) al fotograma real.
    target_face_x = models.FloatField(null=True, blank=True)
    target_face_y = models.FloatField(null=True, blank=True)
    output_s3_key = models.TextField(null=True, blank=True)
    output_file_size_bytes = models.BigIntegerField(null=True, blank=True)
    remote_job_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    model_used = models.CharField(max_length=60, default='facefusion-inswapper_128_fp16')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    progress_pct = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    credits_used = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='faceswap_job_user_created'),
            models.Index(fields=['status', 'updated_at'], name='faceswap_job_status_upd'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(status__in=['queued', 'processing']),
                name='unique_active_faceswap_job',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(source_type='template', template__isnull=False)
                    | models.Q(source_type='upload', template__isnull=True)
                ),
                name='faceswap_job_source_consistent',
            ),
        ]

    def __str__(self):
        return f'FaceSwapJob {self.id} ({self.status})'

    @property
    def has_result(self) -> bool:
        """True si el job terminó y su MP4 está en R2."""
        return self.status == 'completed' and self.output_s3_key is not None
