"""Vistas para exportación de proyectos Mix y consulta de estado."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.credits.services.credit_service import InsufficientCreditsError
from apps.mix.models import MixExport, MixProject
from apps.mix.services.export_service import request_mix_export
from ml.storage_client import generate_presigned_url


class MixExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mix_id):
        try:
            mix = MixProject.objects.get(id=mix_id, user=request.user, deleted_at__isnull=True)
        except MixProject.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            export = request_mix_export(mix, request.user, request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except InsufficientCreditsError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_402_PAYMENT_REQUIRED)

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
            'status': export.status,
            'format': export.format,
            'error_message': export.error_message,
        }
        if export.status == 'ready' and export.output_s3_key:
            data['download_url'] = generate_presigned_url(export.output_s3_key, expiry_seconds=3600)
        return Response(data)
