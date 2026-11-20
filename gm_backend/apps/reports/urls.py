from django.urls import path

from apps.reports.views import (
    AdminUserUpdateView,
    AuditLogView,
    DashboardReportView,
    TopSongsView,
    UsageReportView,
    UsersListView,
)

urlpatterns = [
    path('dashboard/', DashboardReportView.as_view(), name='reports-dashboard'),
    path('usage/', UsageReportView.as_view(), name='reports-usage'),
    path('top-songs/', TopSongsView.as_view(), name='reports-top-songs'),
    path('audit-logs/', AuditLogView.as_view(), name='reports-audit-logs'),
    path('users/', UsersListView.as_view(), name='reports-users'),
    path('users/<uuid:pk>/', AdminUserUpdateView.as_view(), name='reports-user-detail'),
]
