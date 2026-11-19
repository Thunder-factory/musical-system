from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin
from apps.faceswap.models import FaceSwapJob, FaceSwapTemplate
from apps.faceswap.serializers import (
    AdminTemplateSerializer,
    AdminTemplateWriteSerializer,
    FaceSwapJobSerializer,
    TemplateSerializer,
    first_error,
)
from apps.faceswap.services import faceswap_service, template_service
from apps.faceswap.services.faceswap_service import (
    ActiveJobError,
    FaceSwapRequestError,
    InsufficientCreditsError,
    JobNotDeletableError,
    JobNotReadyError,
    PhotoValidationError,
    TemplateUnavailableError,
    VideoValidationError,
)
from apps.faceswap.services.template_service import TemplateValidationError

JOB_NOT_FOUND = {'error': 'Job not found'}
TEMPLATE_NOT_FOUND = {'error': 'Plantilla no encontrada.'}
BAD_REQUEST_ERRORS = (
    FaceSwapRequestError, PhotoValidationError, VideoValidationError, TemplateValidationError,
)


def _error(exc: Exception, code: int) -> Response:
    return Response({'error': str(exc)}, status=code)


class TemplateListView(APIView):
    """
    Catálogo de plantillas activas para el usuario.

    GET /api/faceswap/templates/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        templates = FaceSwapTemplate.objects.filter(is_active=True, deleted_at__isnull=True)
        return Response(TemplateSerializer(templates, many=True).data)


class FaceSwapJobListCreateView(APIView):
    """
    Lista los videos del usuario o crea un face swap nuevo.

    GET  /api/faceswap/jobs/
    POST /api/faceswap/jobs/  (multipart: photo, consent, template_id | video)
    Reserva 3 créditos y encola el job; responde 201 con el job_id.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        jobs = FaceSwapJob.objects.filter(
            user=request.user, deleted_at__isnull=True
        ).select_related('template')
        return Response(FaceSwapJobSerializer(jobs, many=True).data)

    def post(self, request):
        try:
            job = faceswap_service.request_face_swap(
                request.user,
                photo=request.FILES.get('photo'),
                consent=request.data.get('consent'),
                template_id=request.data.get('template_id') or None,
                video=request.FILES.get('video'),
            )
            return Response({'job_id': str(job.id), 'status': job.status}, status=201)
        except BAD_REQUEST_ERRORS as e:
            return _error(e, status.HTTP_400_BAD_REQUEST)
        except InsufficientCreditsError as e:
            return _error(e, status.HTTP_402_PAYMENT_REQUIRED)
        except TemplateUnavailableError as e:
            return _error(e, status.HTTP_404_NOT_FOUND)
        except ActiveJobError as e:
            return _error(e, status.HTTP_409_CONFLICT)
        except Exception as e:
            return _error(e, status.HTTP_500_INTERNAL_SERVER_ERROR)


class FaceSwapJobDetailView(APIView):
    """
    Estado de un job propio o borrado lógico del mismo.

    GET    /api/faceswap/jobs/<id>/
    DELETE /api/faceswap/jobs/<id>/  (409 si está en cola o procesando)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            job = faceswap_service.get_user_job(request.user, id)
        except FaceSwapJob.DoesNotExist:
            return Response(JOB_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return Response(FaceSwapJobSerializer(job).data)

    def delete(self, request, id):
        try:
            faceswap_service.delete_job(request.user, id)
        except FaceSwapJob.DoesNotExist:
            return Response(JOB_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        except JobNotDeletableError as e:
            return _error(e, status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FaceSwapResultUrlView(APIView):
    """
    URL firmada (1 h) del MP4 resultante.

    GET /api/faceswap/jobs/<id>/result-url/?download=1
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        download = request.query_params.get('download') == '1'
        try:
            url = faceswap_service.get_result_url(request.user, id, download=download)
        except FaceSwapJob.DoesNotExist:
            return Response(JOB_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        except JobNotReadyError as e:
            return _error(e, status.HTTP_409_CONFLICT)
        return Response({'url': url})


class AdminTemplateListCreateView(APIView):
    """
    Catálogo completo (incluye inactivas) y alta de plantillas.

    GET  /api/faceswap/admin/templates/
    POST /api/faceswap/admin/templates/  (multipart: title, video, thumbnail?, ref_time_s?,
         is_active?)
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        templates = FaceSwapTemplate.objects.filter(deleted_at__isnull=True)
        return Response(AdminTemplateSerializer(templates, many=True).data)

    def post(self, request):
        serializer = AdminTemplateWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': first_error(serializer.errors)}, status=400)
        try:
            template = template_service.create_template(
                **serializer.validated_data,
                video=request.FILES.get('video'),
                thumbnail=request.FILES.get('thumbnail'),
            )
        except BAD_REQUEST_ERRORS as e:
            return _error(e, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return _error(e, status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(AdminTemplateSerializer(template).data, status=201)


class AdminTemplateDetailView(APIView):
    """
    Edición parcial y borrado lógico de una plantilla.

    PATCH  /api/faceswap/admin/templates/<id>/  (title?, ref_time_s?, is_active?, thumbnail?)
    DELETE /api/faceswap/admin/templates/<id>/
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, id):
        serializer = AdminTemplateWriteSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'error': first_error(serializer.errors)}, status=400)
        try:
            template = template_service.update_template(
                id, **serializer.validated_data, thumbnail=request.FILES.get('thumbnail')
            )
        except FaceSwapTemplate.DoesNotExist:
            return Response(TEMPLATE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        except BAD_REQUEST_ERRORS as e:
            return _error(e, status.HTTP_400_BAD_REQUEST)
        return Response(AdminTemplateSerializer(template).data)

    def delete(self, request, id):
        try:
            template_service.soft_delete_template(id)
        except FaceSwapTemplate.DoesNotExist:
            return Response(TEMPLATE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
