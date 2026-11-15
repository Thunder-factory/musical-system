from unittest import TestCase
from unittest.mock import Mock, patch


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


class DemucsClaimTests(TestCase):
    @patch('ml.modal_demucs_server.stem_job_status', new_callable=FakeDict)
    def test_same_client_job_id_has_one_claim(self, status):
        from ml.modal_demucs_server import _claim_job

        first = _claim_job('client-1')
        second = _claim_job('client-1')

        self.assertEqual(first, second)
        self.assertEqual(status.values['client:client-1']['job_id'], first)

    @patch('ml.modal_demucs_server.stem_job_status', new_callable=FakeDict)
    @patch('ml.modal_demucs_server.DemucsServer')
    def test_spawn_failure_is_retryable_without_second_concurrent_spawn(self, server, status):
        from ml.modal_demucs_server import _claim_job, _spawn_if_needed

        request = {'s3_key': 'songs/source.wav', 'client_job_id': 'client-2'}
        job_id = _claim_job('client-2')
        server.return_value.process.spawn.side_effect = RuntimeError('spawn down')

        with self.assertRaisesRegex(RuntimeError, 'spawn down'):
            _spawn_if_needed(request, job_id)

        self.assertEqual(status.values[job_id]['status'], 'failed')
        self.assertTrue(status.values[job_id]['retryable'])

        server.return_value.process.spawn.side_effect = None
        _spawn_if_needed(request, job_id)
        self.assertEqual(server.return_value.process.spawn.call_count, 2)

    @patch('ml.modal_demucs_server._now', return_value=500)
    @patch('ml.modal_demucs_server.stem_job_status', new_callable=FakeDict)
    @patch('ml.modal_demucs_server.DemucsServer')
    def test_expired_spawn_lease_can_be_recovered(self, server, status, _now):
        from ml.modal_demucs_server import _claim_job, _spawn_if_needed

        request = {'s3_key': 'songs/source.wav', 'client_job_id': 'client-stale'}
        job_id = _claim_job('client-stale')
        status.values[f'spawn:{job_id}'] = {'created_at': 1, 'expires_at': 10}

        _spawn_if_needed(request, job_id)

        server.return_value.process.spawn.assert_called_once_with(
            request, job_id, status.values[f'spawn:{job_id}']['lease_id']
        )

    @patch('ml.modal_demucs_server._now', return_value=500)
    @patch('ml.modal_demucs_server.stem_job_status', new_callable=FakeDict)
    @patch('ml.modal_demucs_server.DemucsServer')
    def test_stale_processing_is_recovered_by_one_spawn(self, server, status, _now):
        from ml.modal_demucs_server import _spawn_if_needed

        job_id = 'job-processing-stale'
        request = {'s3_key': 'songs/source.wav', 'client_job_id': 'client-stale-processing'}
        status.values[job_id] = {
            'status': 'processing',
            'updated_at': -5000,
            'expires_at': 5000,
            'client_job_id': request['client_job_id'],
        }

        _spawn_if_needed(request, job_id)
        _spawn_if_needed(request, job_id)

        self.assertEqual(server.return_value.process.spawn.call_count, 1)

    @patch('ml.modal_demucs_server._now', return_value=500)
    @patch('ml.modal_demucs_server.stem_job_status', new_callable=FakeDict)
    @patch('ml.modal_demucs_server.DemucsServer')
    def test_active_worker_lease_blocks_recovery(self, server, status, _now):
        from ml.modal_demucs_server import _spawn_if_needed

        job_id = 'job-worker-alive'
        request = {'s3_key': 'songs/source.wav', 'client_job_id': 'client-worker-alive'}
        status.values[job_id] = {
            'status': 'processing',
            'updated_at': -5000,
            'expires_at': 5000,
            'client_job_id': request['client_job_id'],
        }
        status.values[f'worker:{job_id}'] = {
            'lease_id': 'worker-1',
            'expires_at': 1000,
        }

        _spawn_if_needed(request, job_id)

        server.return_value.process.spawn.assert_not_called()

    @patch('ml.modal_demucs_server.stem_job_status', new_callable=FakeDict)
    def test_old_worker_cannot_own_replaced_lease(self, status):
        from ml.modal_demucs_server import _worker_owns_job

        status.values['worker:job-1'] = {'lease_id': 'new-worker'}

        self.assertFalse(_worker_owns_job('job-1', 'old-worker'))
        self.assertTrue(_worker_owns_job('job-1', 'new-worker'))

    @patch('ml.modal_demucs_server.stem_job_status', new_callable=FakeDict)
    def test_spawn_owner_can_publish_initialization_failure(self, status):
        from ml.modal_demucs_server import _worker_can_fail_job

        status.values['spawn:job-2'] = {'lease_id': 'lease-2'}

        self.assertTrue(_worker_can_fail_job('job-2', 'lease-2'))
        self.assertFalse(_worker_can_fail_job('job-2', 'old-lease'))
