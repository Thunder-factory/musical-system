from django.urls import path
from apps.mix.views import (
    MixProjectListCreateView, MixProjectDetailView,
    MixClipView, MixExternalClipUploadView, MixClipDetailView, MixClipPlayUrlView,
    MixClipSplitView, MixReorderView,
    MixExportView, MixExportStatusView,
)

urlpatterns = [
    path('projects/',                                    MixProjectListCreateView.as_view(), name='mix-projects'),
    path('projects/<uuid:mix_id>/',                      MixProjectDetailView.as_view(),     name='mix-project-detail'),
    path('projects/<uuid:mix_id>/clips/',                MixClipView.as_view(),              name='mix-clips'),
    path('projects/<uuid:mix_id>/clips/upload/',         MixExternalClipUploadView.as_view(), name='mix-external-clip-upload'),
    path('projects/<uuid:mix_id>/clips/<uuid:clip_id>/', MixClipDetailView.as_view(),        name='mix-clip-detail'),
    path('projects/<uuid:mix_id>/clips/<uuid:clip_id>/play-url/', MixClipPlayUrlView.as_view(), name='mix-clip-play-url'),
    path('projects/<uuid:mix_id>/clips/<uuid:clip_id>/split/', MixClipSplitView.as_view(),   name='mix-clip-split'),
    path('projects/<uuid:mix_id>/reorder/',              MixReorderView.as_view(),           name='mix-reorder'),
    path('projects/<uuid:mix_id>/export/',               MixExportView.as_view(),            name='mix-export'),
    path('exports/<uuid:export_id>/',                    MixExportStatusView.as_view(),      name='mix-export-status'),
]
