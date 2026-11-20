from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from ml.modal_client import (
    ModalGenerationError,
    get_faceswap_job_status,
    submit_faceswap_job,
    submit_stem_job,
)


class ModalClientTests(SimpleTestCase):
    @patch('ml.modal_client.time.sleep')
    @patch('ml.modal_client.requests.post')
    def test_submit_retries_timeout_without_changing_client_id(self, post, _sleep):
        response = Mock(ok=True)
        response.json.return_value = {
            'remote_job_id': 'remote-1',
            'status': 'queued',
            'progress_pct': 0,
        }
        post.side_effect = [requests.Timeout(), response]

        payload = {'s3_key': 'songs/source.wav', 'client_job_id': 'job-1'}
        result = submit_stem_job('https://modal.example/stems', payload)

        self.assertEqual(result['remote_job_id'], 'remote-1')
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs['json']['client_job_id'], 'job-1')
        self.assertEqual(post.call_args_list[1].kwargs['json']['client_job_id'], 'job-1')

    @patch('ml.modal_client.time.sleep')
    @patch('ml.modal_client.requests.post')
    def test_submit_faceswap_is_async_and_retries_with_same_client_id(self, post, _sleep):
        response = Mock(ok=True)
        response.json.return_value = {
            'remote_job_id': 'remote-fs', 'status': 'queued', 'progress_pct': 0,
        }
        post.side_effect = [requests.Timeout(), response]

        payload = {
            'client_job_id': 'job-fs',
            'photo_s3_key': 'faceswap/uploads/photos/a.jpg',
            'video_s3_key': 'faceswap/templates/videos/b.mp4',
            'ref_time_s': 2.5,
        }
        result = submit_faceswap_job('https://modal.example/faceswap', payload)

        self.assertEqual(result['remote_job_id'], 'remote-fs')
        self.assertEqual(post.call_count, 2)
        for call in post.call_args_list:
            self.assertTrue(call.kwargs['json']['async'])
            self.assertEqual(call.kwargs['json']['client_job_id'], 'job-fs')

    @patch('ml.modal_client.requests.post')
    def test_faceswap_status_requires_progress(self, post):
        response = Mock(ok=True)
        response.json.return_value = {'status': 'processing'}
        post.return_value = response

        with self.assertRaises(ModalGenerationError):
            get_faceswap_job_status('https://modal.example/faceswap', 'remote-fs')
        self.assertEqual(post.call_args.kwargs['json']['action'], 'status')
