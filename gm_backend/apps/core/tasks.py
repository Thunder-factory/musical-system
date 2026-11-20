"""Tareas Celery para recuperación periódica de operaciones abandonadas."""

from celery import shared_task

from apps.core.services.karaoke_recovery import recover_karaoke_track as _recover_karaoke_track
from apps.core.services.recovery_helpers import (
    cleanup_unreferenced_storage_keys as _cleanup_unreferenced_storage_keys,
    fail_stale_operation as _fail_stale_operation,
    recover_one as _recover_one,
    remote_state as _remote_state,
    stale_cutoff as _stale,
)
from apps.core.services.recovery_service import recover_abandoned_operations_service


@shared_task
def recover_abandoned_operations():
    """Cierra trabajos abandonados sin reserva confirmable y reencola los recuperables."""
    return recover_abandoned_operations_service()
