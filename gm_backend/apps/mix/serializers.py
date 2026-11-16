from rest_framework import serializers
from apps.mix.models import MixProject, MixClip, MixExport
from apps.songs.serializers import SongLibrarySerializer


class MixClipSerializer(serializers.ModelSerializer):
    song_detail   = SongLibrarySerializer(source='song', read_only=True)
    duration_ms   = serializers.ReadOnlyField()
    is_external   = serializers.SerializerMethodField()

    def get_is_external(self, obj):
        return bool(obj.custom_audio_s3_key)

    class Meta:
        model  = MixClip
        fields = [
            'id', 'position', 'timeline_start_ms', 'start_time_ms', 'end_time_ms',
            'fade_in_ms', 'fade_out_ms', 'volume',
            'is_muted', 'is_solo',
            'song', 'stem_file', 'is_external', 'custom_audio_name',
            'custom_audio_content_type', 'custom_audio_size_bytes', 'custom_audio_duration_ms',
            'song_detail', 'duration_ms', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'duration_ms', 'song_detail']


class MixProjectSerializer(serializers.ModelSerializer):
    clips      = MixClipSerializer(many=True, read_only=True)
    clip_count = serializers.SerializerMethodField()

    class Meta:
        model  = MixProject
        fields = [
            'id', 'title', 'description', 'bpm', 'status',
            'output_s3_key', 'duration_seconds',
            'clips', 'clip_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'output_s3_key', 'duration_seconds', 'clips', 'clip_count', 'created_at', 'updated_at']

    def get_clip_count(self, obj):
        return obj.clips.count()


class MixExportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MixExport
        fields = ['id', 'format', 'quality', 'status', 'credits_used', 'error_message', 'created_at']
        read_only_fields = ['id', 'status', 'credits_used', 'error_message', 'created_at']
