from unittest.mock import Mock, patch

from django.test import SimpleTestCase
import requests

from ml.modal_client import submit_stem_job


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
