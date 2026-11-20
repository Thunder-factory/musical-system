from rest_framework import serializers
from apps.songs.models import Song
from apps.songs.serializers import TagSerializer


class CommunitySongSerializer(serializers.ModelSerializer):
    """Serializer para el feed público. Incluye datos del autor."""
    tags          = TagSerializer(many=True, read_only=True)
    user_name     = serializers.SerializerMethodField()
    is_liked      = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model  = Song
        fields = [
            'id', 'title', 'description', 'thumbnail_s3_key', 'thumbnail_url',
            'tags', 'play_count', 'like_count',
            'user_name', 'is_liked', 'created_at',
        ]

    def get_user_name(self, obj):
        return obj.user.full_name if obj.user else '—'

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.liked_by.filter(user=request.user).exists()

    def get_thumbnail_url(self, obj):
        if not obj.thumbnail_s3_key:
            return None
        try:
            from ml.storage_client import generate_presigned_url
            return generate_presigned_url(obj.thumbnail_s3_key, expiry_seconds=3600)
        except Exception:
            return None
