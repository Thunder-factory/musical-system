from django.urls import path

from apps.translations.views import (
    TranslationConfigView,
    TranslationCreateView,
    TranslationDownloadUrlView,
    TranslationJobDetailView,
    TranslationJobListView,
)

urlpatterns = [
    path('', TranslationCreateView.as_view(), name='translation-create'),
    path('config/', TranslationConfigView.as_view(), name='translation-config'),
    path('jobs/', TranslationJobListView.as_view(), name='translation-job-list'),
    path('jobs/<uuid:id>/', TranslationJobDetailView.as_view(), name='translation-job-detail'),
    path('jobs/<uuid:id>/download-url/', TranslationDownloadUrlView.as_view(), name='translation-download-url'),
]
