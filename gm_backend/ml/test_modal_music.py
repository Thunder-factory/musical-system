from unittest import TestCase
from unittest.mock import patch
import sys
import types


class FakeDict:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def __setitem__(self, key, value):
        self.values[key] = value

    def put(self, key, value, *, skip_if_exists=False):
        if skip_if_exists and key in self.values:
            return False
        self.values[key] = value
        return True

    def pop(self, key, default=None):
        return self.values.pop(key, default)


class MusicGenerationIdempotencyTests(TestCase):
    def test_same_client_job_id_reuses_active_job(self):
        sys.modules.setdefault('prompts', types.SimpleNamespace(
            LYRICS_GENERATOR_PROMPT='{description}',
            PROMPT_GENERATOR_PROMPT='{user_prompt}',
        ))
        from ml import modal_music_server
        from ml.modal_music_server import _claim_music_job

        with patch.object(modal_music_server, 'music_job_status', FakeDict()):
            first = _claim_music_job('generation-1')
            second = _claim_music_job('generation-1')

        self.assertEqual(first, second)

    @patch('time.time', return_value=500)
    def test_expired_job_can_be_reclaimed(self, _time):
        sys.modules.setdefault('prompts', types.SimpleNamespace(
            LYRICS_GENERATOR_PROMPT='{description}',
            PROMPT_GENERATOR_PROMPT='{user_prompt}',
        ))
        from ml.modal_music_server import _claim_music_job

        status = FakeDict()
        status.values['client:generation-stale'] = {
            'job_id': 'old-job',
        }
        status.values['old-job'] = {
            'status': 'processing',
            'expires_at': 10,
        }

        from ml import modal_music_server
        with patch.object(modal_music_server, 'music_job_status', status):
            result = _claim_music_job('generation-stale')

        self.assertNotEqual(result, 'old-job')
