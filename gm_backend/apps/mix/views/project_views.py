"""Vistas de listado, creación y detalle para proyectos Mix."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.mix.models import MixProject
from apps.mix.serializers import MixProjectSerializer
from apps.mix.services.mix_service import create_mix_project, delete_mix


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

            mix.tags.set(Tag.objects.filter(id__in=request.data['tag_ids']))
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
