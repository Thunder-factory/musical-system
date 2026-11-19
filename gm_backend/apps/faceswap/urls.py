from django.urls import path

from apps.faceswap.views import (
    AdminTemplateDetailView,
    AdminTemplateListCreateView,
    FaceSwapJobDetailView,
    FaceSwapJobListCreateView,
    FaceSwapResultUrlView,
    TemplateListView,
)

urlpatterns = [
    path('templates/', TemplateListView.as_view(), name='faceswap-templates'),
    path('jobs/', FaceSwapJobListCreateView.as_view(), name='faceswap-jobs'),
    path('jobs/<uuid:id>/', FaceSwapJobDetailView.as_view(), name='faceswap-job-detail'),
    path(
        'jobs/<uuid:id>/result-url/',
        FaceSwapResultUrlView.as_view(),
        name='faceswap-result-url',
    ),
    path(
        'admin/templates/',
        AdminTemplateListCreateView.as_view(),
        name='faceswap-admin-templates',
    ),
    path(
        'admin/templates/<uuid:id>/',
        AdminTemplateDetailView.as_view(),
        name='faceswap-admin-template',
    ),
]
