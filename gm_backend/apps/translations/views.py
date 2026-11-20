import logging
import os

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.translations.models import TranslationJob
from apps.translations.services.translation_service import (
    InsufficientCreditsError,
    TranslationValidationError,
    get_translation_config,
    request_translation,
)
from ml.storage_client import generate_presigned_url

logger = logging.getLogger(__name__)

DOWNLOADABLE_FILES = {
    # nombre pedido → (campo del modelo, content-type, nombre de descarga)
    'video': ('result_video_key', 'video/mp4', 'traduccion.mp4'),
    'audio': ('result_audio_key', 'audio/mpeg', 'voz.mp3'),
}


def serialize_job(job: TranslationJob) -> dict:
    return {
        'id': str(job.id),
        'source_filename': job.source_filename,
        'source_file_size_bytes': job.source_file_size_bytes,
        'source_duration_seconds': job.source_duration_seconds,
        'target_language': job.target_language,
        'song_title': job.song_title,
        'song_artist': job.song_artist,
        'remote_job_id': job.remote_job_id,
        'mode': job.mode,
        'status': job.status,
        'stage': job.stage,
        'progress_pct': job.progress_pct,
        'credits_used': job.credits_used,
        'error_message': job.error_message,
        'lyrics': job.lyrics,
        'details': job.details,
        'has_video': bool(job.result_video_key),
        'has_audio': bool(job.result_audio_key),
        'created_at': job.created_at,
        'started_at': job.started_at,
        'completed_at': job.completed_at,
    }


class TranslationConfigView(APIView):
    """GET /api/translations/config/ — idiomas, límites y costo en créditos."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_translation_config())


class TranslationCreateView(APIView):
    """
    POST /api/translations/
    Multipart: file (video), target_language (en|es|fr|zh), title y artist opcionales.
    Valida el video, reserva créditos, lo sube a R2 y encola el doblaje.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No se envió ningún video.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            job = request_translation(
                request.user,
                file,
                os.path.basename(file.name),
                request.data.get('target_language', ''),
                song_title=request.data.get('title'),
                song_artist=request.data.get('artist'),
            )
        except TranslationValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except InsufficientCreditsError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except Exception:
            logger.exception('No se pudo crear la traducción')
            return Response(
                {'error': 'No se pudo iniciar la traducción. Intenta de nuevo.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({'job_id': str(job.id)}, status=status.HTTP_201_CREATED)


class TranslationJobListView(APIView):
    """GET /api/translations/jobs/ — historial del usuario autenticado."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = TranslationJob.objects.filter(user=request.user, deleted_at__isnull=True)[:50]
        return Response([serialize_job(job) for job in jobs])


class TranslationJobDetailView(APIView):
    """GET /api/translations/jobs/<id>/ — estado, etapa, progreso y resultado."""

    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        job = TranslationJob.objects.filter(id=id, user=request.user, deleted_at__isnull=True).first()
        if job is None:
            return Response({'error': 'Traducción no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_job(job))


class TranslationDownloadUrlView(APIView):
    """
    GET /api/translations/jobs/<id>/download-url/?file=video|audio[&download=1]
    Devuelve una URL temporal de R2 para reproducir o descargar el resultado.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        requested = request.query_params.get('file', 'video')
        if requested not in DOWNLOADABLE_FILES:
            return Response({'error': 'Archivo no válido.'}, status=status.HTTP_400_BAD_REQUEST)

        job = TranslationJob.objects.filter(
            id=id, user=request.user, status='completed', deleted_at__isnull=True,
        ).first()
        if job is None:
            return Response({'error': 'Traducción no disponible.'}, status=status.HTTP_404_NOT_FOUND)

        field, content_type, download_name = DOWNLOADABLE_FILES[requested]
        key = getattr(job, field)
        if not key:
            return Response({'error': 'Archivo no disponible.'}, status=status.HTTP_404_NOT_FOUND)

        download = request.query_params.get('download') == '1'
        url = generate_presigned_url(
            key,
            response_content_disposition=f'attachment; filename="{download_name}"' if download else None,
            response_content_type=content_type,
        )
        return Response({'url': url})
