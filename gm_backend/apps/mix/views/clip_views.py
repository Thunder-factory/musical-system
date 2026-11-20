"""Vistas para gestión de clips en la línea de tiempo de Mix."""

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.mix.models import MixClip, MixProject
from apps.mix.serializers import MixClipSerializer
from apps.mix.services.clip_request_service import (
    add_clip_from_payload,
    patch_clip_from_payload,
)
from apps.mix.services.mix_service import (
    AudioValidationError,
    add_external_clip,
    remove_clip,
    reorder_clips,
    split_clip,
)
from apps.stems.services.stem_service import FileTooLargeError
from ml.storage_client import generate_presigned_url


class MixClipView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mix_id):
        try:
            mix = MixProject.objects.get(id=mix_id, user=request.user, deleted_at__isnull=True)
        except MixProject.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            clip = add_clip_from_payload(mix, request.user, request.data)
        except (TypeError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MixClipSerializer(clip).data, status=status.HTTP_201_CREATED)


class MixExternalClipUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, mix_id):
        try:
            mix = MixProject.objects.get(id=mix_id, user=request.user, deleted_at__isnull=True)
        except MixProject.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        audio_file = request.FILES.get('file')
        if not audio_file:
            return Response({'detail': 'file es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            end_time_value = request.data.get('end_time_ms')
            clip = add_external_clip(
                mix_project=mix,
                user=request.user,
                audio_file=audio_file,
                position=int(request.data.get('position', mix.clips.count())),
                timeline_start_ms=int(request.data.get('timeline_start_ms', 0)),
                start_time_ms=int(request.data.get('start_time_ms', 0)),
                end_time_ms=int(end_time_value) if end_time_value not in (None, '') else None,
                fade_in_ms=int(request.data.get('fade_in_ms', 0)),
                fade_out_ms=int(request.data.get('fade_out_ms', 0)),
                volume=float(request.data.get('volume', 1.0)),
            )
        except (AudioValidationError, FileTooLargeError, TypeError, ValueError, PermissionError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MixClipSerializer(clip).data, status=status.HTTP_201_CREATED)


class MixClipDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_clip(self, request, mix_id, clip_id):
        try:
            return MixClip.objects.select_related('mix_project').get(
                id=clip_id,
                mix_project__id=mix_id,
                mix_project__user=request.user,
                mix_project__deleted_at__isnull=True,
            )
        except MixClip.DoesNotExist:
            return None

    def patch(self, request, mix_id, clip_id):
        clip = self._get_clip(request, mix_id, clip_id)
        if not clip:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            clip = patch_clip_from_payload(clip, request.user, request.data)
        except (TypeError, ValueError, PermissionError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MixClipSerializer(clip).data)

    def delete(self, request, mix_id, clip_id):
        clip = self._get_clip(request, mix_id, clip_id)
        if not clip:
            return Response(status=status.HTTP_404_NOT_FOUND)
        remove_clip(clip.id, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MixClipPlayUrlView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, mix_id, clip_id):
        try:
            clip = MixClip.objects.get(
                id=clip_id,
                mix_project__id=mix_id,
                mix_project__user=request.user,
                mix_project__deleted_at__isnull=True,
            )
        except MixClip.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not clip.custom_audio_s3_key:
            return Response(
                {'detail': 'El clip no contiene un archivo externo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        url = generate_presigned_url(
            clip.custom_audio_s3_key,
            expiry_seconds=3600,
            response_content_type=clip.custom_audio_content_type or 'audio/mpeg',
        )
        return Response({'url': url})


class MixClipSplitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mix_id, clip_id):
        try:
            clip = MixClip.objects.select_related('mix_project').get(
                id=clip_id,
                mix_project__id=mix_id,
                mix_project__user=request.user,
                mix_project__deleted_at__isnull=True,
            )
        except MixClip.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            playhead_ms = int(request.data['playhead_ms'])
            left_clip, right_clip = split_clip(clip, user=request.user, playhead_ms=playhead_ms)
        except KeyError:
            return Response({'detail': 'playhead_ms es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError, PermissionError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {'left_clip': MixClipSerializer(left_clip).data, 'right_clip': MixClipSerializer(right_clip).data},
            status=status.HTTP_201_CREATED,
        )


class MixReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mix_id):
        try:
            mix = MixProject.objects.get(id=mix_id, user=request.user, deleted_at__isnull=True)
        except MixProject.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        clip_ids = request.data.get('clip_ids', [])
        if not clip_ids:
            return Response({'detail': 'clip_ids es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            reorder_clips(mix, clip_ids)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'ok'})
