import hmac
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.credits.services.credit_service import InsufficientCreditsError
from apps.humming.models import HummingJob
from apps.humming.serializers import (
    HummingChooseSerializer,
    HummingJobSerializer,
    HummingUploadSerializer,
)
from apps.humming.services import (
    HummingValidationError,
    apply_worker_result,
    choose_version,
    create_humming_job,
)
from apps.humming.tasks import handle_retry_action
from apps.songs.serializers import SongLibrarySerializer

logger = logging.getLogger(__name__)

WORKER_TOKEN_HEADER = 'X-Worker-Token'


class HummingJobListCreateView(generics.ListAPIView):
    """
    GET  /api/humming/ — tarareos del usuario.
    POST /api/humming/ — sube un tarareo (multipart: file, title?) y lo encola.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = HummingJobSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return HummingJob.objects.filter(user=self.request.user, deleted_at__isnull=True)

    def post(self, request):
        serializer = HummingUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = create_humming_job(
                request.user,
                serializer.validated_data['file'],
                title=serializer.validated_data.get('title'),
            )
        except InsufficientCreditsError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except HummingValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('No se pudo registrar el tarareo')
            return Response(
                {'detail': 'No se pudo guardar el tarareo.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(HummingJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class HummingJobDetailView(generics.RetrieveAPIView):
    """GET /api/humming/{id}/ — estado, progreso, versiones y descargas."""

    permission_classes = [IsAuthenticated]
    serializer_class = HummingJobSerializer

    def get_queryset(self):
        return HummingJob.objects.filter(user=self.request.user, deleted_at__isnull=True)


class HummingChooseView(APIView):
    """POST /api/humming/{id}/choose/ — {version, title?} → crea la Song en la biblioteca."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        job = get_object_or_404(
            HummingJob, pk=pk, user=request.user, deleted_at__isnull=True
        )
        serializer = HummingChooseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            song = choose_version(
                job,
                serializer.validated_data['version'],
                title=serializer.validated_data.get('title'),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            SongLibrarySerializer(song, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class HummingCallbackView(APIView):
    """
    POST /api/humming/callback/ — llamado SOLO por el worker gm_tarareo.

    Autenticado con el secreto compartido en X-Worker-Token (no con JWT).
    Si TARAREO_CALLBACK_TOKEN no está configurado se rechaza todo.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        expected = settings.TARAREO_CALLBACK_TOKEN
        received = request.headers.get(WORKER_TOKEN_HEADER, '')
        if not expected or not hmac.compare_digest(received.encode(), expected.encode()):
            return Response(status=status.HTTP_403_FORBIDDEN)

        data = request.data if isinstance(request.data, dict) else {}
        job_id = data.get('jobId')
        if not job_id or not HummingJob.objects.filter(id=job_id).exists():
            return Response({'detail': 'Job desconocido.'}, status=status.HTTP_404_NOT_FOUND)

        action = apply_worker_result(str(job_id), data)
        # El polling ya está en marcha desde el despacho: acá solo se atiende un reintento.
        handle_retry_action(str(job_id), action, data)
        return Response(status=status.HTTP_204_NO_CONTENT)
