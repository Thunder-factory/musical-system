"""Llamada al modelo de lenguaje del asistente y saneamiento de su salida."""
import json
import logging

try:  # Si la imagen aún no tiene el SDK, el servidor arranca y el asistente responde 503.
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None
from django.conf import settings

from apps.assistant.services.knowledge import ALLOWED_ROUTES, GUIDE, MAX_ACTIONS

logger = logging.getLogger(__name__)

MAX_TOKENS = 800
FALLBACK_REPLY = (
    'No puedo ayudarte con eso. Pregúntame sobre las funciones de MusicAI, '
    'tus créditos o cómo empezar a crear música.'
)

RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'reply': {'type': 'string'},
        'actions': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'label': {'type': 'string'},
                    'route': {'type': 'string', 'enum': list(ALLOWED_ROUTES)},
                },
                'required': ['label', 'route'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['reply', 'actions'],
    'additionalProperties': False,
}


class AssistantUnavailableError(Exception):
    """No hay clave de API configurada (se responde 503)."""


class AssistantUpstreamError(Exception):
    """La API del modelo falló o devolvió algo inválido (se responde 502)."""


def _client():
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY, timeout=20.0, max_retries=1,
    )


def clean_actions(raw_actions) -> list:
    """Filtra rutas fuera de la lista, etiquetas vacías y recorta a MAX_ACTIONS."""
    actions = []
    for item in raw_actions if isinstance(raw_actions, list) else []:
        if not isinstance(item, dict):
            continue
        label = str(item.get('label', '')).strip()[:60]
        route = item.get('route')
        if label and route in ALLOWED_ROUTES:
            actions.append({'label': label, 'route': route})
        if len(actions) == MAX_ACTIONS:
            break
    return actions


def _log_usage(response) -> None:
    usage = getattr(response, 'usage', None)
    if usage is None:
        return
    logger.info(
        'assistant usage model=%s input=%s output=%s cache_read=%s cache_write=%s',
        getattr(response, 'model', settings.ASSISTANT_MODEL),
        usage.input_tokens, usage.output_tokens,
        usage.cache_read_input_tokens, usage.cache_creation_input_tokens,
    )


def _parse(response) -> dict:
    if response.stop_reason in ('refusal', 'max_tokens'):
        logger.info('assistant fallback stop_reason=%s', response.stop_reason)
        return {'reply': FALLBACK_REPLY, 'actions': []}
    text = next((b.text for b in response.content if b.type == 'text'), None)
    try:
        data = json.loads(text or '')
    except (TypeError, ValueError) as exc:
        raise AssistantUpstreamError('Salida no es JSON válido.') from exc
    reply = str(data.get('reply', '')).strip() if isinstance(data, dict) else ''
    if not reply:
        raise AssistantUpstreamError('Respuesta vacía.')
    return {'reply': reply, 'actions': clean_actions(data.get('actions'))}


def ask_assistant(messages: list, user_context: str) -> dict:
    """Envía el historial al modelo y devuelve {'reply', 'actions'} saneado."""
    if anthropic is None or not settings.ANTHROPIC_API_KEY:
        raise AssistantUnavailableError()
    try:
        response = _client().messages.create(
            model=settings.ASSISTANT_MODEL,
            max_tokens=MAX_TOKENS,
            thinking={'type': 'disabled'},
            output_config={
                'effort': 'low',
                'format': {'type': 'json_schema', 'schema': RESPONSE_SCHEMA},
            },
            system=[
                {'type': 'text', 'text': GUIDE, 'cache_control': {'type': 'ephemeral'}},
                {'type': 'text', 'text': user_context},
            ],
            messages=messages,
        )
    except (anthropic.RateLimitError, anthropic.APIStatusError,
            anthropic.APIConnectionError) as exc:
        logger.warning('assistant upstream error: %s', type(exc).__name__)
        raise AssistantUpstreamError(str(exc)) from exc
    _log_usage(response)
    return _parse(response)
