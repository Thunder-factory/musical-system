"""Funciones auxiliares compartidas para recuperación de operaciones asíncronas."""

from __future__ import annotations

from datetime import timedelta
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def stale_cutoff(seconds_name: str, default: int = 1800):
    """Calcula el instante límite a partir del cual una operación se considera vencida."""
    return timezone.now() - timedelta(
        seconds=getattr(settings, seconds_name, default)
    )


def remote_state(
    kind: str,
    remote_job_id: str | None,
    endpoint_url: str | None = None,
) -> str:
    """Consulta el estado remoto de forma tolerante a fallos y sin bloqueos en BD."""
    if not remote_job_id:
        return 'unknown'
    if kind == 'generation' and not endpoint_url:
        return 'unavailable'
    try:
        if kind == 'generation':
            from ml.modal_client import get_music_job_status

            response = get_music_job_status(endpoint_url, remote_job_id)
        elif kind == 'faceswap':
            from ml.modal_client import get_faceswap_job_status

            response = get_faceswap_job_status(
                settings.MODAL_ENDPOINT_FACESWAP,
                remote_job_id,
            )
        else:
            from ml.modal_client import get_stem_job_status

            response = get_stem_job_status(
                settings.MODAL_ENDPOINT_SEPARATE_STEMS,
                remote_job_id,
            )
        return response.get('status') or 'unknown'
    except Exception:
        logger.exception(
            'No se pudo consultar el trabajo remoto durante la recuperación: %s %s',
            kind,
            remote_job_id,
        )
        return 'unavailable'


def cleanup_unreferenced_storage_keys(keys) -> None:
    """Elimina de R2 solo claves huérfanas que no estén referenciadas por ninguna canción."""
    from apps.songs.models import Song
    from ml.storage_client import delete_file

    for key in {key for key in keys if key}:
        if Song.objects.filter(
            Q(audio_s3_key=key) | Q(thumbnail_s3_key=key)
        ).exists():
            continue
        try:
            delete_file(key)
        except Exception:
            logger.exception('No se pudo limpiar el archivo huérfano %s', key)


def recover_one(
    *,
    model,
    object_id,
    user_id,
    reference_type: str,
    stale_check,
    enqueue,
    remote_state: str,
    failure_message: str,
    final_statuses: set[str],
    on_failed=None,
    cleanup_failed=None,
) -> tuple[str, int]:
    """Recupera una operación mediante una transacción corta con orden de bloqueo fijo."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import release_reservation
    from apps.users.models import User

    action = 'ignored'
    released_count = 0
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user_id)
        operation = model.objects.select_for_update().get(pk=object_id)
        if operation.status in final_statuses or not stale_check(operation):
            return 'ignored', 0

        reservation = CreditReservation.objects.select_for_update().filter(
            user=locked_user,
            reference_id=object_id,
            reference_type=reference_type,
        ).first()
        now = timezone.now()
        reservation_valid = bool(
            reservation and reservation.status == 'confirmed'
        ) or bool(
            reservation
            and reservation.status == 'reserved'
            and (reservation.expires_at is None or reservation.expires_at > now)
        )

        if reservation_valid:
            operation.status = 'queued'
            updates = ['status', 'updated_at']
            if hasattr(operation, 'error_message'):
                operation.error_message = None
                updates.append('error_message')
            operation.save(update_fields=updates)
            action = 'requeue'
        else:
            if reservation and reservation.status == 'reserved':
                release_reservation(str(reservation.id))
                released_count = 1

            operation.status = 'failed'
            updates = ['status', 'updated_at']
            if hasattr(operation, 'error_message'):
                operation.error_message = (
                    f'{failure_message} Estado remoto: {remote_state}.'
                )
                updates.append('error_message')
            if hasattr(operation, 'completed_at'):
                operation.completed_at = now
                updates.append('completed_at')
            operation.save(update_fields=updates)
            if on_failed:
                on_failed()
            action = 'failed'

    if action == 'requeue':
        enqueue()
    elif action == 'failed' and cleanup_failed:
        cleanup_failed()
    return action, released_count


def fail_stale_operation(
    *,
    model,
    object_id,
    user_id,
    reference_type: str,
    stale_check,
    failure_message: str,
    final_statuses: set[str],
    extra_updates: dict | None = None,
) -> tuple[str, int]:
    """Marca como fallida una operación vencida y libera su reserva de créditos."""
    from apps.credits.models import CreditReservation
    from apps.credits.services.credit_service import release_reservation
    from apps.users.models import User

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user_id)
        operation = model.objects.select_for_update().get(pk=object_id)
        if operation.status in final_statuses or not stale_check(operation):
            return 'ignored', 0

        reservation = CreditReservation.objects.select_for_update().filter(
            user=locked_user,
            reference_id=object_id,
            reference_type=reference_type,
        ).first()
        released_count = 0
        if reservation and reservation.status == 'reserved':
            release_reservation(str(reservation.id))
            released_count = 1

        now = timezone.now()
        operation.status = 'failed'
        updates = ['status', 'updated_at']
        if hasattr(operation, 'error_message'):
            operation.error_message = failure_message
            updates.append('error_message')
        if hasattr(operation, 'completed_at'):
            operation.completed_at = now
            updates.append('completed_at')
        for field, value in (extra_updates or {}).items():
            if hasattr(operation, field):
                setattr(operation, field, value)
                if field not in updates:
                    updates.append(field)
        operation.save(update_fields=updates)
        return 'failed', released_count

