"""Paquete de servicios del dominio de tarareo."""

import requests

from apps.credits.services.credit_service import (
    InsufficientCreditsError,
    confirm_reservation,
    reserve_credits,
)
from apps.humming.services.choice_service import _delete_keys, _find_version, choose_version
from apps.humming.services.constants import (
    ALLOWED_INPUT_EXTENSIONS,
    CONTRACT_VERSION,
    DispatchOutcome,
    ERROR_INTERNAL,
    ERROR_INVALID_INPUT,
    HummingValidationError,
    OUTPUT_CONTENT_TYPES,
    RESERVATION_TYPE,
    WORKER_STATUS_COMPLETED,
    WORKER_STATUS_FAILED,
    WORKER_STATUS_PROCESSING,
    WorkerRejectedError,
    WorkerUnavailableError,
    _job_prefix,
    output_key,
)
from apps.humming.services.job_service import (
    _validate_upload,
    create_humming_job,
    mark_dispatched,
    mark_failed,
    requeue_for_retry,
)
from apps.humming.services.result_service import (
    _confirm_credits,
    _output_name,
    _partial_metadata,
    _start_ai,
    apply_worker_result,
    metadata_from_analysis,
)
from apps.humming.services.worker_client import (
    _presigned_put,
    build_dispatch_payload,
    fetch_worker_status,
    send_to_worker,
)
from ml.storage_client import (
    download_fileobj,
    generate_presigned_url,
    get_storage_bucket,
    get_storage_client,
)

__all__ = [
    'ALLOWED_INPUT_EXTENSIONS',
    'CONTRACT_VERSION',
    'DispatchOutcome',
    'ERROR_INTERNAL',
    'ERROR_INVALID_INPUT',
    'HummingValidationError',
    'InsufficientCreditsError',
    'OUTPUT_CONTENT_TYPES',
    'RESERVATION_TYPE',
    'WORKER_STATUS_COMPLETED',
    'WORKER_STATUS_FAILED',
    'WORKER_STATUS_PROCESSING',
    'WorkerRejectedError',
    'WorkerUnavailableError',
    'apply_worker_result',
    'build_dispatch_payload',
    'choose_version',
    'confirm_reservation',
    'create_humming_job',
    'download_fileobj',
    'fetch_worker_status',
    'generate_presigned_url',
    'get_storage_bucket',
    'get_storage_client',
    'mark_dispatched',
    'mark_failed',
    'metadata_from_analysis',
    'output_key',
    'requests',
    'requeue_for_retry',
    'reserve_credits',
    'send_to_worker',
]
