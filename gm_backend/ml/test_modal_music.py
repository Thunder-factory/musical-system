from unittest import TestCase
from unittest.mock import Mock, patch
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
    def test_same_client_job_id_recovers_cached_result(self):
        sys.modules.setdefault('prompts', types.SimpleNamespace(
            LYRICS_GENERATOR_PROMPT='{description}',
            PROMPT_GENERATOR_PROMPT='{user_prompt}',
        ))
        from ml import modal_music_server
        from ml.modal_music_server import (
            GenerateMusicResponseS3,
            _run_idempotent_music_job,
        )

        producer = Mock(return_value=GenerateMusicResponseS3(
            s3_key='songs/result.wav',
            cover_image_s3_key='songs/result.png',
            categories=['pop'],
        ))

        with patch.object(modal_music_server, 'music_job_status', FakeDict()):
            first = _run_idempotent_music_job('generation-1', producer)
            second = _run_idempotent_music_job('generation-1', producer)

        self.assertEqual(first.s3_key, second.s3_key)
        producer.assert_called_once_with()

    @patch('time.time', return_value=500)
    def test_expired_processing_record_can_be_reclaimed(self, _time):
        sys.modules.setdefault('prompts', types.SimpleNamespace(
            LYRICS_GENERATOR_PROMPT='{description}',
            PROMPT_GENERATOR_PROMPT='{user_prompt}',
        ))
        from ml.modal_music_server import (
            GenerateMusicResponseS3,
            _run_idempotent_music_job,
        )

        status = FakeDict()
        status.values['music:generation-stale'] = {
            'status': 'processing',
            'expires_at': 10,
        }
        producer = Mock(return_value=GenerateMusicResponseS3(
            s3_key='songs/recovered.wav',
            cover_image_s3_key='songs/recovered.png',
            categories=[],
        ))

        from ml import modal_music_server
        with patch.object(modal_music_server, 'music_job_status', status):
            result = _run_idempotent_music_job('generation-stale', producer)

        self.assertEqual(result.s3_key, 'songs/recovered.wav')
        producer.assert_called_once_with()
