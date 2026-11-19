from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


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


class FaceSwapClaimTests(TestCase):
    @patch('ml.modal_faceswap_server.faceswap_job_status', new_callable=FakeDict)
    def test_same_client_job_id_has_one_claim(self, status):
        from ml.modal_faceswap_server import _claim_job

        first = _claim_job('client-1')
        second = _claim_job('client-1')

        self.assertEqual(first, second)
        self.assertEqual(status.values['client:client-1']['job_id'], first)
        self.assertIsNone(status.values[first]['output_s3_key'])

    @patch('ml.modal_faceswap_server.faceswap_job_status', new_callable=FakeDict)
    @patch('ml.modal_faceswap_server.FaceSwapServer')
    def test_spawn_failure_is_retryable_without_second_concurrent_spawn(self, server, status):
        from ml.modal_faceswap_server import _claim_job, _spawn_if_needed

        request = {
            'photo_s3_key': 'faceswap/uploads/photos/a.jpg',
            'video_s3_key': 'faceswap/templates/videos/b.mp4',
            'client_job_id': 'client-2',
        }
        job_id = _claim_job('client-2')
        server.return_value.process.spawn.side_effect = RuntimeError('spawn down')

        with self.assertRaisesRegex(RuntimeError, 'spawn down'):
            _spawn_if_needed(request, job_id)

        self.assertEqual(status.values[job_id]['status'], 'failed')
        self.assertTrue(status.values[job_id]['retryable'])

        server.return_value.process.spawn.side_effect = None
        _spawn_if_needed(request, job_id)
        _spawn_if_needed(request, job_id)
        self.assertEqual(server.return_value.process.spawn.call_count, 2)


class FaceFusionCommandTests(TestCase):
    def test_reference_mode_with_ref_time(self):
        from ml.modal_faceswap_server import _facefusion_command

        cmd = _facefusion_command(Path('p.jpg'), Path('v.mp4'), Path('o.mp4'), ref_time_s=2.5)

        self.assertIn('reference', cmd)
        frame_index = cmd.index('--reference-frame-number')
        self.assertEqual(cmd[frame_index + 1], '62')
        for token in ('inswapper_128_fp16', 'codeformer', '45', '256x256'):
            self.assertIn(token, cmd)
        self.assertNotIn('large-small', cmd)

    def test_largest_face_mode_without_ref_time(self):
        from ml.modal_faceswap_server import _facefusion_command

        cmd = _facefusion_command(Path('p.jpg'), Path('v.mp4'), Path('o.mp4'), ref_time_s=None)

        self.assertIn('one', cmd)
        self.assertIn('large-small', cmd)
        self.assertNotIn('--reference-frame-number', cmd)

    def test_progress_mapping(self):
        from ml.modal_faceswap_server import _map_progress

        self.assertEqual([_map_progress(p) for p in (0, 50, 100)], [10, 50, 90])


class FaceSwapKeyValidationTests(TestCase):
    def test_rejects_invalid_keys(self):
        from ml.modal_faceswap_server import _validate_key

        for key in ('', '/abs', 'a/../b'):
            with self.assertRaises(ValueError):
                _validate_key(key)
        self.assertEqual(_validate_key(' faceswap/a.jpg '), 'faceswap/a.jpg')
