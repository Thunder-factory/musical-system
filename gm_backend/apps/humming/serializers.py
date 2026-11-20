from rest_framework import serializers

from apps.humming.models import HummingEnhancement, HummingJob
from apps.humming.styles import CUSTOM_STYLE_KEY, DEFAULT_FIDELITY, FIDELITY_STRENGTH
from ml.storage_client import generate_presigned_url

URL_SECONDS = 3600

# Metadatos del worker que se exponen al frontend (el resto queda para análisis interno).
PUBLIC_METADATA_FIELDS = (
    'bpm', 'tonalidad', 'acordes', 'estilo', 'estiloMensaje', 'estiloAmbiguo',
    'duracionCancionSegundos', 'motivo', 'grafico',
)


def _similarity(item: HummingEnhancement, number: int) -> dict | None:
    """{"puntaje", "nivel"} de la variante `number` (1..n) si ya se midió."""
    values = item.variant_similarity or []
    value = values[number - 1] if 0 < number <= len(values) else None
    return value if value and value.get('puntaje') is not None else None


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


class HummingEnhanceSerializer(serializers.Serializer):
    # Opcional: sin versión, la base se elige sola según el estilo.
    version = serializers.IntegerField(min_value=1, max_value=3, required=False, allow_null=True)
    style = serializers.CharField(max_length=40)
    custom_style = serializers.CharField(max_length=200, required=False, allow_blank=True)
    fidelity = serializers.ChoiceField(
        choices=sorted(FIDELITY_STRENGTH), required=False, default=DEFAULT_FIDELITY
    )

    def validate(self, attrs):
        if attrs['style'] == CUSTOM_STYLE_KEY and not attrs.get('custom_style', '').strip():
            raise serializers.ValidationError({'custom_style': 'Describe el estilo que quieres.'})
        return attrs


class HummingChooseVariantSerializer(serializers.Serializer):
    variant = serializers.IntegerField(min_value=1, max_value=3)


class HummingEnhancementSerializer(serializers.ModelSerializer):
    variants = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    song_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = HummingEnhancement
        fields = [
            'id', 'version_number', 'style_key', 'style_label', 'fidelity', 'status',
            'progress', 'error_message', 'credits_used', 'variants', 'chosen_variant',
            'song_id', 'cover_url', 'created_at', 'completed_at',
        ]
        read_only_fields = fields

    def get_variants(self, item):
        """Variantes para escuchar; tras elegir, solo queda la elegida (las otras se borraron)."""
        if item.status != 'completed':
            return []
        return [
            {
                'number': numero,
                'audio_url': generate_presigned_url(key, URL_SECONDS),
                'similarity': _similarity(item, numero),
            }
            for numero, key in enumerate(item.variant_keys or [], start=1)
            if item.chosen_variant in (None, numero)
        ]

    def get_cover_url(self, item):
        if item.status != 'completed' or not item.cover_s3_key:
            return None
        return generate_presigned_url(item.cover_s3_key, URL_SECONDS)


class HummingJobSerializer(serializers.ModelSerializer):
    metadata = serializers.SerializerMethodField()
    versions = serializers.SerializerMethodField()
    downloads = serializers.SerializerMethodField()
    song_id = serializers.UUIDField(read_only=True, allow_null=True)
    enhancements = serializers.SerializerMethodField()

    class Meta:
        model = HummingJob
        fields = [
            'id', 'title', 'status', 'progress', 'stage', 'error_message', 'error_code',
            'metadata', 'versions', 'downloads', 'chosen_version', 'song_id',
            'enhancements', 'credits_used', 'created_at', 'completed_at',
        ]
        read_only_fields = fields

    def get_enhancements(self, job):
        items = job.enhancements.filter(automatic=False).select_related('song')
        return HummingEnhancementSerializer(items, many=True).data

    @staticmethod
    def _ai(job, number):
        item = next(
            (e for e in job.enhancements.all() if e.automatic and e.version_number == number), None
        )
        if not item:
            return None
        listo = item.status == 'completed' and item.variant_keys
        return {
            'status': item.status,
            'audio_url': generate_presigned_url(item.variant_keys[0], URL_SECONDS) if listo else None,
            'cover_url': (generate_presigned_url(item.cover_s3_key, URL_SECONDS)
                          if listo and item.cover_s3_key else None),
            'similarity': _similarity(item, 1) if listo else None,
        }

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
                # Versión producida con IA (si está activa); audio_url es la de FluidSynth.
                'ai': self._ai(job, number),
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
