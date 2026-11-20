from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin
from apps.reports.services import (
    get_admin_dashboard_metrics,
    list_admin_users,
    update_admin_user,
)


class DashboardReportView(APIView):
    """Métricas agregadas reales del sistema para el dashboard administrativo."""

    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(get_admin_dashboard_metrics())


class UsageReportView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        from apps.songs.models import GenerationJob, Song
        from apps.users.models import User

        now = timezone.now()
        last_30 = now - timedelta(days=30)

        return Response({
            'total_users': User.objects.filter(deleted_at__isnull=True).count(),
            'new_users_30d': User.objects.filter(created_at__gte=last_30).count(),
            'total_songs_generated': Song.objects.filter(status='ready').count(),
            'songs_last_30d': Song.objects.filter(status='ready', created_at__gte=last_30).count(),
            'failed_jobs_30d': GenerationJob.objects.filter(status='failed', created_at__gte=last_30).count(),
            'public_songs': Song.objects.filter(is_public=True, status='ready').count(),
        })


class TopSongsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        from apps.songs.models import Song
        from apps.songs.serializers import SongLibrarySerializer

        songs = Song.objects.filter(status='ready', is_public=True).order_by('-play_count')[:20]
        return Response(SongLibrarySerializer(songs, many=True).data)


class AuditLogView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        from apps.audit.models import AuditLog
        from apps.audit.serializers import AuditLogSerializer

        logs = AuditLog.objects.all().order_by('-created_at')
        action = request.query_params.get('action')
        user_id = request.query_params.get('user_id')
        if action:
            logs = logs.filter(action=action)
        if user_id:
            logs = logs.filter(user_id=user_id)
        return Response(AuditLogSerializer(logs[:100], many=True).data)


class UsersListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        search = request.query_params.get('search', '')
        return Response(list_admin_users(search=search))


class AdminUserUpdateView(APIView):
    """Permite a un administrador actualizar is_staff o is_active de otro usuario."""

    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        updated = update_admin_user(
            acting_user=request.user,
            user_id=pk,
            payload=request.data,
            request=request,
        )
        return Response(updated)
