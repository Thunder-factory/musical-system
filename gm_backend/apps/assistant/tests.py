import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.assistant.services.context import build_user_context
from apps.assistant.services.knowledge import GUIDE
from apps.credits.models import CreditPlan, UserSubscription
from apps.users.models import User

URL = '/api/assistant/chat/'
CLIENT_PATH = 'apps.assistant.services.llm_client.anthropic.Anthropic'


def fake_response(payload=None, stop_reason='end_turn', text=None):
    body = text if text is not None else json.dumps(payload)
    usage = SimpleNamespace(input_tokens=10, output_tokens=20,
                            cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=body)],
        stop_reason=stop_reason, usage=usage, model='test-model',
    )


def mock_client(mock_cls, response=None, side_effect=None):
    instance = MagicMock()
    instance.messages.create.return_value = response
    if side_effect is not None:
        instance.messages.create.side_effect = side_effect
    mock_cls.return_value = instance
    return instance.messages.create


@override_settings(ANTHROPIC_API_KEY='test-key', ASSISTANT_MODEL='test-model')
class AssistantChatTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='nuevo@test.com', password='x12345678', full_name='Ana Prueba',
            credit_balance=4,
        )
        plan = CreditPlan.objects.create(slug='pro-t', name='Pro', credits_per_month=30,
                                         price_usd=9)
        UserSubscription.objects.create(user=self.user, plan=plan, status='active')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def post(self, messages=None, page='/inicio'):
        messages = messages or [{'role': 'user', 'content': '¿Cómo creo una canción?'}]
        return self.api.post(URL, {'messages': messages, 'page': page}, format='json')

    @patch(CLIENT_PATH)
    def test_ok_returns_reply_and_actions(self, mock_cls):
        create = mock_client(mock_cls, fake_response({
            'reply': 'Ve a Crear canción.',
            'actions': [{'label': 'Ir a Crear canción', 'route': '/create'}],
        }))
        res = self.post()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['actions'], [{'label': 'Ir a Crear canción', 'route': '/create'}])
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs['model'], 'test-model')
        self.assertEqual(kwargs['thinking'], {'type': 'disabled'})
        self.assertEqual(kwargs['output_config']['format']['type'], 'json_schema')
        self.assertEqual(kwargs['system'][0]['text'], GUIDE)
        self.assertIn('cache_control', kwargs['system'][0])
        self.assertNotIn('cache_control', kwargs['system'][1])

    @patch(CLIENT_PATH)
    def test_context_includes_credits_plan_and_page(self, mock_cls):
        create = mock_client(mock_cls, fake_response({'reply': 'Hola', 'actions': []}))
        self.post(page='/stems')
        dynamic = create.call_args.kwargs['system'][1]['text']
        self.assertIn('Saldo de créditos: 4', dynamic)
        self.assertIn('Plan: Pro', dynamic)
        self.assertIn('Página actual: /stems', dynamic)
        self.assertIn('Ana Prueba', dynamic)

    def test_context_without_subscription(self):
        user = User.objects.create_user(email='s@test.com', password='x12345678', full_name='')
        text = build_user_context(user, '')
        self.assertIn('sin plan activo', text)
        self.assertIn('Saldo de créditos: 0', text)

    @patch(CLIENT_PATH)
    def test_filters_invalid_routes_and_caps_three_actions(self, mock_cls):
        actions = [{'label': 'Malo', 'route': '/admin'}, {'label': 'Ext', 'route': 'https://x.com'}]
        actions += [{'label': f'Ir {i}', 'route': '/library'} for i in range(5)]
        mock_client(mock_cls, fake_response({'reply': 'Listo', 'actions': actions}))
        res = self.post()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['actions']), 3)
        self.assertTrue(all(a['route'] == '/library' for a in res.json()['actions']))

    @patch(CLIENT_PATH)
    def test_refusal_and_max_tokens_return_fallback(self, mock_cls):
        for reason in ('refusal', 'max_tokens'):
            mock_client(mock_cls, fake_response(text='{"reply": "cort', stop_reason=reason))
            res = self.post()
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()['actions'], [])
            self.assertTrue(res.json()['reply'])

    @patch(CLIENT_PATH)
    def test_invalid_json_returns_502(self, mock_cls):
        mock_client(mock_cls, fake_response(text='no es json'))
        self.assertEqual(self.post().status_code, 502)

    @patch(CLIENT_PATH)
    def test_sdk_errors_return_502(self, mock_cls):
        request = httpx.Request('POST', 'https://api.test/v1/messages')
        errors = [
            anthropic.APIConnectionError(request=request),
            anthropic.RateLimitError('rate', response=httpx.Response(429, request=request), body=None),
            anthropic.InternalServerError('boom', response=httpx.Response(500, request=request), body=None),
        ]
        for error in errors:
            mock_client(mock_cls, side_effect=error)
            res = self.post()
            self.assertEqual(res.status_code, 502)
            self.assertIn('no pudo responder', res.json()['detail'])

    @override_settings(ANTHROPIC_API_KEY='')
    @patch(CLIENT_PATH)
    def test_without_key_returns_503(self, mock_cls):
        res = self.post()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()['detail'], 'El asistente no está disponible.')
        mock_cls.assert_not_called()

    def test_requires_authentication(self):
        res = APIClient().post(URL, {'messages': [{'role': 'user', 'content': 'hola'}]},
                               format='json')
        self.assertEqual(res.status_code, 401)

    @patch(CLIENT_PATH)
    def test_validation_errors(self, mock_cls):
        too_long = 'x' * 1001
        cases = [
            [],
            [{'role': 'assistant', 'content': 'hola'}],
            [{'role': 'user', 'content': 'a'}, {'role': 'user', 'content': 'b'}],
            [{'role': 'user', 'content': 'a'}, {'role': 'assistant', 'content': 'b'}],
            [{'role': 'user', 'content': too_long}],
            [{'role': 'user', 'content': ''}],
            [{'role': 'system', 'content': 'a'}],
            [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': 'm'} for i in range(13)],
        ]
        for messages in cases:
            res = self.api.post(URL, {'messages': messages}, format='json')
            self.assertEqual(res.status_code, 400, messages[:1])
        res = self.post(page='/' + 'p' * 100)
        self.assertEqual(res.status_code, 400)
        mock_cls.assert_not_called()

    def test_guide_is_stable_and_lists_routes(self):
        self.assertNotIn('Ana Prueba', GUIDE)
        for route in ('/create', '/payments', '/karaoke', '/traducciones'):
            self.assertIn(route, GUIDE)
