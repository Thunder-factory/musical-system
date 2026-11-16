from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from django.db import transaction

from apps.mix.models import MixProject, MixClip, MixExport
from apps.mix.serializers import MixProjectSerializer, MixClipSerializer, MixExportSerializer
from apps.mix.services.mix_service import (
    AudioValidationError,
    add_clip,
    add_external_clip,
    create_mix_project,
    delete_mix,
    remove_clip,
    reorder_clips,
    split_clip,
    update_clip,
)
from apps.stems.services.stem_service import FileTooLargeError
from ml.storage_client import generate_presigned_url


class MixProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = MixProject.objects.filter(user=request.user, deleted_at__isnull=True)
        return Response(MixProjectSerializer(qs, many=True).data)

    def post(self, request):
        mix = create_mix_project(
            user=request.user,
            title=request.data.get('title', 'Nuevo mix'),
            description=request.data.get('description'),
            bpm=request.data.get('bpm'),
        )
        return Response(MixProjectSerializer(mix).data, status=status.HTTP_201_CREATED)


class MixProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_mix(self, request, mix_id):
        try:
            return MixProject.objects.get(id=mix_id, user=request.user, deleted_at__isnull=True)
        except MixProject.DoesNotExist:
            return None

    def get(self, request, mix_id):
        mix = self._get_mix(request, mix_id)
        if not mix:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(MixProjectSerializer(mix).data)

    def patch(self, request, mix_id):
        mix = self._get_mix(request, mix_id)
        if not mix:
            return Response(status=status.HTTP_404_NOT_FOUND)

        for field in ['title', 'description', 'bpm']:
            if field in request.data:
                setattr(mix, field, request.data[field])
        mix.save()

        if 'tag_ids' in request.data:
            from apps.songs.models import Tag
            tag_ids = request.data['tag_ids']
            mix.tags.set(Tag.objects.filter(id__in=tag_ids))

        return Response(MixProjectSerializer(mix).data)

    def delete(self, request, mix_id):
        mix = self._get_mix(request, mix_id)
        if not mix:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            delete_mix(mix, request.user)
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MixClipView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mix_id):
        try:
            mix = MixProject.objects.get(id=mix_id, user=request.user, deleted_at__isnull=True)
        except MixProject.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        end_time_ms = request.data.get('end_time_ms')
        if end_time_ms is None:
            return Response({'detail': 'end_time_ms es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        is_muted = request.data.get('is_muted', False)
        is_solo = request.data.get('is_solo', False)
        if not isinstance(is_muted, bool) or not isinstance(is_solo, bool):
            return Response(
                {'detail': 'is_muted e is_solo deben ser booleanos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            clip = add_clip(
                mix_project=mix,
                user=request.user,
                position=int(request.data.get('position', mix.clips.count())),
                timeline_start_ms=int(request.data.get('timeline_start_ms', 0)),
                song_id=request.data.get('song_id'),
                stem_file_id=request.data.get('stem_file_id'),
                start_time_ms=int(request.data.get('start_time_ms', 0)),
                end_time_ms=int(end_time_ms),
                fade_in_ms=int(request.data.get('fade_in_ms', 0)),
                fade_out_ms=int(request.data.get('fade_out_ms', 0)),
                volume=float(request.data.get('volume', 1.0)),
                is_muted=is_muted,
                is_solo=is_solo,
            )
        except (TypeError, ValueError) as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MixClipSerializer(clip).data, status=status.HTTP_201_CREATED)


class MixExternalClipUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, mix_id):
        try:
            mix = MixProject.objects.get(
                id=mix_id,
                user=request.user,
                deleted_at__isnull=True,
            )
        except MixProject.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        audio_file = request.FILES.get('file')
        if not audio_file:
            return Response(
                {'detail': 'file es requerido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

        requested_position = None
        changes = {}
        try:
            for field in [
                'timeline_start_ms', 'start_time_ms', 'end_time_ms', 'fade_in_ms', 'fade_out_ms',
                'position', 'song_id', 'stem_file_id', 'is_muted', 'is_solo',
            ]:
                if field in request.data:
                    if field in {'song_id', 'stem_file_id'}:
                        changes[field] = request.data[field]
                    elif field in {'is_muted', 'is_solo'}:
                        if not isinstance(request.data[field], bool):
                            raise ValueError(f'{field} debe ser booleano.')
                        changes[field] = request.data[field]
                    else:
                        changes[field] = int(request.data[field])
            if 'volume' in request.data:
                changes['volume'] = float(request.data['volume'])
        except (TypeError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if 'song_id' in changes and 'stem_file_id' not in changes:
            changes['stem_file_id'] = None
        if 'stem_file_id' in changes and 'song_id' not in changes:
            changes['song_id'] = None
        requested_position = changes.pop('position', None)
        try:
            with transaction.atomic():
                update_clip(clip, user=request.user, **changes)
                if requested_position is not None:
                    clip_count = clip.mix_project.clips.count()
                    if requested_position < 0 or requested_position >= clip_count:
                        raise ValueError('position está fuera del rango de clips.')
                    ordered_ids = list(
                        MixClip.objects.filter(mix_project=clip.mix_project)
                        .order_by('position')
                        .values_list('id', flat=True)
                    )
                    ordered_ids.remove(clip.id)
                    ordered_ids.insert(requested_position, clip.id)
                    reorder_clips(clip.mix_project, ordered_ids)
                    clip.refresh_from_db()
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

        return Response(
            {
                'url': generate_presigned_url(
                    clip.custom_audio_s3_key,
                    expiry_seconds=3600,
                    response_content_type=clip.custom_audio_content_type or 'audio/mpeg',
                )
            }
        )


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
            left_clip, right_clip = split_clip(
                clip,
                user=request.user,
                playhead_ms=playhead_ms,
            )
        except KeyError:
            return Response(
                {'detail': 'playhead_ms es requerido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (TypeError, ValueError, PermissionError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'left_clip': MixClipSerializer(left_clip).data,
                'right_clip': MixClipSerializer(right_clip).data,
            },
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


class MixExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mix_id):
        try:
            mix = MixProject.objects.get(id=mix_id, user=request.user, deleted_at__isnull=True)
        except MixProject.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not mix.clips.exists():
            return Response({'detail': 'El mix no tiene clips.'}, status=status.HTTP_400_BAD_REQUEST)

        export_format = request.data.get('format', 'mp3')
        quality = request.data.get('quality', '320k')
        if export_format not in {'mp3', 'wav'}:
            return Response({'detail': 'format debe ser mp3 o wav.'}, status=status.HTTP_400_BAD_REQUEST)
        if quality not in {'128k', '320k', 'lossless'}:
            return Response({'detail': 'quality no es válida.'}, status=status.HTTP_400_BAD_REQUEST)
        if export_format == 'wav' and quality != 'lossless':
            return Response({'detail': 'Los archivos WAV deben usar calidad lossless.'}, status=status.HTTP_400_BAD_REQUEST)
        if export_format == 'mp3' and quality == 'lossless':
            return Response({'detail': 'La calidad lossless requiere formato WAV.'}, status=status.HTTP_400_BAD_REQUEST)

        requested_muted_ids = request.data.get('muted_clip_ids', [])
        requested_solo_ids = request.data.get('solo_clip_ids', [])
        if not isinstance(requested_muted_ids, list) or not isinstance(requested_solo_ids, list):
            return Response(
                {'detail': 'muted_clip_ids y solo_clip_ids deben ser listas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mix_clip_ids = {str(clip_id) for clip_id in mix.clips.values_list('id', flat=True)}
        if not set(map(str, requested_muted_ids)).issubset(mix_clip_ids):
            return Response(
                {'detail': 'Hay clips silenciados que no pertenecen al mix.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not set(map(str, requested_solo_ids)).issubset(mix_clip_ids):
            return Response(
                {'detail': 'Hay clips solo que no pertenecen al mix.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                export = MixExport.objects.create(
                    mix_project=mix,
                    format=export_format,
                    quality=quality,
                    status='queued',
                )
                from apps.credits.services.credit_service import reserve_credits
                reserve_credits(
                    request.user,
                    amount=3,
                    reference_id=str(export.id),
                    reference_type='mix_export',
                )
        except Exception as exc:
            from apps.credits.services.credit_service import InsufficientCreditsError
            if isinstance(exc, InsufficientCreditsError):
                return Response({'detail': str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
            raise

        from apps.mix.tasks import render_mix
        tag_ids = list(mix.tags.values_list('id', flat=True))

        render_mix.delay(
            str(export.id),
            tag_ids=tag_ids,
            muted_clip_ids=list(map(str, requested_muted_ids)),
            solo_clip_ids=list(map(str, requested_solo_ids)),
        )

        return Response({'export_id': str(export.id)}, status=status.HTTP_202_ACCEPTED)


class MixExportStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, export_id):
        try:
            export = MixExport.objects.select_related('mix_project').get(
                id=export_id,
                mix_project__user=request.user,
            )
        except MixExport.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        data = {
            'status':        export.status,
            'format':        export.format,
            'error_message': export.error_message,
        }

        if export.status == 'ready' and export.output_s3_key:
            from ml.storage_client import generate_presigned_url
            data['download_url'] = generate_presigned_url(export.output_s3_key, expiry_seconds=3600)

        return Response(data)
