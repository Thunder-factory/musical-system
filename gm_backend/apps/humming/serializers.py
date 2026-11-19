from rest_framework import serializers

from apps.humming.models import HummingJob
from ml.storage_client import generate_presigned_url

URL_SECONDS = 3600

# Metadatos del worker que se exponen al frontend (el resto queda para análisis interno).
PUBLIC_METADATA_FIELDS = (
    'bpm', 'tonalidad', 'acordes', 'estilo', 'estiloMensaje', 'estiloAmbiguo',
    'duracionCancionSegundos', 'motivo',
)


def _signed(job: HummingJob, name: str, *, download_name: str | None = None) -> str | None:
    if name not in (job.available_outputs or []):
        return None
    key = (job.output_keys or {}).get(name)
    if not key:
        return None
    disposition = f'attachment; filename="{download_name}"' if download_name else None
    return generate_presigned_url(key, URL_SECONDS, response_content_disposition=disposition)


class HummingUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)


class HummingChooseSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1, max_value=3)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)


class HummingJobSerializer(serializers.ModelSerializer):
    metadata = serializers.SerializerMethodField()
    versions = serializers.SerializerMethodField()
    downloads = serializers.SerializerMethodField()
    song_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = HummingJob
        fields = [
            'id', 'title', 'status', 'progress', 'stage', 'error_message', 'error_code',
            'metadata', 'versions', 'downloads', 'chosen_version', 'song_id',
            'credits_used', 'created_at', 'completed_at',
        ]
        read_only_fields = fields

    def get_metadata(self, job):
        data = job.metadata or {}
        return {field: data[field] for field in PUBLIC_METADATA_FIELDS if field in data}

    def get_versions(self, job):
        """Versiones con su audio listo (pueden llegar de a una mientras procesa)."""
        versions = []
        for version in job.versions:
            song_file = version.get('cancion') or ''
            audio_url = _signed(job, song_file)
            if not audio_url:
                continue
            number = int(version.get('numero', 0))
            arrangement = 'arreglo.mid' if number == 1 else f'arreglo-{number}.mid'
            versions.append({
                'number': number,
                'style': version.get('estilo'),
                'variant': version.get('variante'),
                'score': version.get('puntaje'),
                'audio_url': audio_url,
                'midi_url': _signed(job, arrangement, download_name=f'tarareo-v{number}.mid'),
            })
        return versions

    def get_downloads(self, job):
        if job.status != 'completed':
            return {}
        return {
            'melody_midi_url': _signed(job, 'melodia.mid', download_name='melodia.mid'),
            'score_musicxml_url': _signed(
                job, 'partitura.musicxml', download_name='partitura.musicxml'
            ),
        }
