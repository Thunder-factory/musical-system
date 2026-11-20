from django.contrib import admin

from apps.translations.models import TranslationJob


@admin.register(TranslationJob)
class TranslationJobAdmin(admin.ModelAdmin):
    list_display = (
        'source_filename', 'user', 'target_language', 'status', 'stage',
        'progress_pct', 'mode', 'credits_used', 'created_at',
    )
    list_filter = ('status', 'target_language', 'mode')
    search_fields = ('source_filename', 'user__email', 'remote_job_id')
    readonly_fields = ('id', 'created_at', 'updated_at', 'started_at', 'completed_at')
