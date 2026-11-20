from django.contrib import admin

from apps.humming.models import HummingEnhancement, HummingJob


@admin.register(HummingJob)
class HummingJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'progress', 'stage', 'chosen_version', 'created_at')
    list_filter = ('status', 'error_code')
    search_fields = ('id', 'user__email', 'title')
    readonly_fields = ('created_at', 'updated_at', 'started_at', 'last_heartbeat_at', 'completed_at')


@admin.register(HummingEnhancement)
class HummingEnhancementAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'style_key', 'fidelity', 'status', 'progress', 'created_at')
    list_filter = ('status', 'style_key', 'fidelity')
    search_fields = ('id', 'user__email', 'remote_job_id')
