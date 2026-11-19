from rest_framework import serializers

from apps.faceswap.models import FaceSwapJob, FaceSwapTemplate
from ml.storage_client import generate_presigned_url

REF_TIME_ERROR = 'El segundo de referencia está fuera del video.'


class TemplateSerializer(serializers.ModelSerializer):
    """Plantilla visible para el usuario, con URLs firmadas de 1 h."""

    has_reference = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = FaceSwapTemplate
        fields = [
            'id', 'title', 'duration_seconds', 'has_reference', 'thumbnail_url', 'preview_url',
        ]

    def get_has_reference(self, obj: FaceSwapTemplate) -> bool:
        """True si la plantilla define el segundo de la cara a reemplazar."""
        return obj.ref_time_s is not None

    def get_thumbnail_url(self, obj: FaceSwapTemplate) -> str:
        """URL firmada de la miniatura."""
        return generate_presigned_url(obj.thumbnail_s3_key)

    def get_preview_url(self, obj: FaceSwapTemplate) -> str:
        """URL firmada del video base."""
        return generate_presigned_url(obj.video_s3_key)


class AdminTemplateSerializer(TemplateSerializer):
    """Plantilla para el panel admin (incluye ref_time_s, estado y fechas)."""

    class Meta(TemplateSerializer.Meta):
        fields = [
            *TemplateSerializer.Meta.fields,
            'ref_time_s', 'is_active', 'created_at', 'updated_at',
        ]


class AdminTemplateWriteSerializer(serializers.Serializer):
    """Valida los campos editables de una plantilla (los archivos van aparte)."""

    title = serializers.CharField(
        max_length=120,
        error_messages={
            'required': 'El título es obligatorio.',
            'blank': 'El título es obligatorio.',
            'max_length': 'El título admite como máximo 120 caracteres.',
        },
    )
    ref_time_s = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0,
        error_messages={'invalid': REF_TIME_ERROR, 'min_value': REF_TIME_ERROR},
    )
    # default=True también evita que DRF tome el campo ausente en multipart como False.
    is_active = serializers.BooleanField(required=False, default=True)


class FaceSwapJobSerializer(serializers.ModelSerializer):
    """Job de face swap tal como lo consume el frontend."""

    template = serializers.SerializerMethodField()
    has_result = serializers.BooleanField(read_only=True)

    class Meta:
        model = FaceSwapJob
        fields = [
            'id', 'source_type', 'template', 'source_video_filename', 'source_duration_seconds',
            'model_used', 'remote_job_id', 'status', 'progress_pct', 'credits_used',
            'error_message', 'has_result', 'created_at', 'started_at', 'completed_at',
        ]

    def get_template(self, obj: FaceSwapJob) -> dict | None:
        """Resumen ``{id, title}`` de la plantilla o null si es un clip propio."""
        if not obj.template_id:
            return None
        return {'id': str(obj.template_id), 'title': obj.template.title}


def first_error(errors) -> str:
    """Devuelve el primer mensaje de error de un serializer como texto plano."""
    if isinstance(errors, dict):
        return first_error(next(iter(errors.values()), 'Datos inválidos.'))
    if isinstance(errors, list):
        return first_error(errors[0]) if errors else 'Datos inválidos.'
    return str(errors)
