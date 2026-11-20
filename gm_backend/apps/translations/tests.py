import json
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.credits.models import CreditReservation
from apps.translations.models import TranslationJob
from apps.translations.services.translation_service import (
    TranslationValidationError,
    request_translation,
    validate_video_file,
)
from apps.translations.tasks import poll_translation_job
from apps.users.models import User


def _probe_output(duration=60.0, streams=('video', 'audio')):
    result = MagicMock()
    result.stdout = json.dumps({
        'format': {'duration': str(duration)},
        'streams': [{'codec_type': kind} for kind in streams],
    })
    return result


def _video(name='clip.mp4', content=b'fake-video-bytes'):
    return SimpleUploadedFile(name, content, content_type='video/mp4')


class VideoValidationTests(TestCase):
    @patch('apps.translations.services.translation_service.subprocess.run')
    def test_accepts_valid_video_and_restores_seek(self, run):
        run.return_value = _probe_output(duration=42.5)
        video = _video()
        digest, duration = validate_video_file(video, video.name)
        self.assertEqual(len(digest), 64)
        self.assertEqual(duration, 42.5)
        self.assertEqual(video.tell(), 0)

    def test_rejects_unsupported_extension(self):
        with self.assertRaises(TranslationValidationError):
            validate_video_file(_video('clip.avi'), 'clip.avi')

    @patch('apps.translations.services.translation_service.subprocess.run')
    def test_rejects_video_without_audio(self, run):
        run.return_value = _probe_output(streams=('video',))
        with self.assertRaisesMessage(TranslationValidationError, 'pista de audio'):
            validate_video_file(_video(), 'clip.mp4')

    @override_settings(TRANSLATION_MAX_DURATION_SECONDS=300)
    @patch('apps.translations.services.translation_service.subprocess.run')
    def test_rejects_video_longer_than_five_minutes(self, run):
        run.return_value = _probe_output(duration=301)
        with self.assertRaisesMessage(TranslationValidationError, '5 minutos'):
            validate_video_file(_video(), 'clip.mp4')

    @override_settings(TRANSLATION_MAX_FILE_SIZE_MB=1)
    def test_rejects_file_over_size_limit(self):
        big = _video(content=b'0' * (1024 * 1024 + 1))
        with self.assertRaisesMessage(TranslationValidationError, '1 MB'):
            validate_video_file(big, 'clip.mp4')


@override_settings(TRANSLATION_CREDIT_COST=3)
class RequestTranslationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='traductor@test.com', password='x', credit_balance=5)

    @patch('apps.translations.tasks.process_translation_job.delay')
    @patch('apps.translations.services.translation_service.upload_fileobj', return_value='translations/uploads/a.mp4')
    @patch('apps.translations.services.translation_service.subprocess.run')
    def test_creates_job_reserves_credits_and_enqueues(self, run, upload, delay):
        run.return_value = _probe_output(duration=30)
        job = request_translation(self.user, _video(), 'clip.mp4', 'fr', song_title=' Song ', song_artist='')

        self.assertEqual(job.target_language, 'fr')
        self.assertEqual(job.song_title, 'Song')
        self.assertEqual(job.source_video_key, 'translations/uploads/a.mp4')
        self.assertEqual(job.stage, 'en_cola')
        reservation = CreditReservation.objects.get(reference_id=job.id, reference_type='translation_job')
        self.assertEqual(reservation.amount, 3)
        self.assertEqual(reservation.status, 'reserved')
        delay.assert_called_once_with(str(job.id))

    def test_rejects_unsupported_language(self):
        with self.assertRaisesMessage(TranslationValidationError, 'Idioma no soportado'):
            request_translation(self.user, _video(), 'clip.mp4', 'de')

    @patch('apps.translations.tasks.process_translation_job.delay')
    @patch('apps.translations.services.translation_service.upload_fileobj', return_value='k.mp4')
    @patch('apps.translations.services.translation_service.subprocess.run')
    def test_same_video_and_language_in_progress_returns_existing_job(self, run, _upload, delay):
        run.return_value = _probe_output()
        first = request_translation(self.user, _video(), 'clip.mp4', 'es')
        second = request_translation(self.user, _video(), 'clip.mp4', 'es')
        self.assertEqual(first.id, second.id)
        self.assertEqual(delay.call_count, 1)

    @override_settings(TRANSLATION_REMOTE_TIMEOUT_SECONDS=2400)
    @patch('apps.translations.tasks.process_translation_job.delay')
    @patch('apps.translations.services.translation_service.upload_fileobj', return_value='k.mp4')
    @patch('apps.translations.services.translation_service.subprocess.run')
    def test_stuck_job_past_timeout_does_not_block_a_new_request(self, run, _upload, delay):
        from datetime import timedelta

        from django.utils import timezone

        run.return_value = _probe_output()
        stuck = request_translation(self.user, _video(), 'clip.mp4', 'es')
        TranslationJob.objects.filter(id=stuck.id).update(started_at=timezone.now() - timedelta(seconds=2500))

        fresh = request_translation(self.user, _video(), 'clip.mp4', 'es')

        stuck.refresh_from_db()
        self.assertNotEqual(fresh.id, stuck.id)
        self.assertEqual(stuck.status, 'failed')
        self.assertEqual(
            CreditReservation.objects.get(reference_id=stuck.id).status, 'released',
        )
        self.assertEqual(delay.call_count, 2)

    @override_settings(TRANSLATION_REMOTE_TIMEOUT_SECONDS=2400)
    @patch('apps.translations.tasks.process_translation_job.delay')
    @patch('apps.translations.services.translation_service.upload_fileobj', return_value='k.mp4')
    @patch('apps.translations.services.translation_service.subprocess.run')
    def test_credit_reservation_outlives_the_remote_timeout(self, run, _upload, _delay):
        from django.utils import timezone

        run.return_value = _probe_output()
        job = request_translation(self.user, _video(), 'clip.mp4', 'en')
        reservation = CreditReservation.objects.get(reference_id=job.id)
        self.assertGreater((reservation.expires_at - timezone.now()).total_seconds(), 2400 + 600)


@override_settings(
    MODAL_ENDPOINT_TRANSLATE_VIDEO='https://modal.test/translate',
    TRANSLATION_MODE='simulated',
    TRANSLATION_SING=False,
    TRANSLATION_DEBUG=False,
)
class SubmitTranslationTests(TestCase):
    @patch('apps.translations.tasks._schedule_poll')
    @patch('ml.modal_client.submit_translation_job')
    def test_submit_sends_modal_contract_and_stores_remote_id(self, submit, schedule):
        from apps.translations.tasks import process_translation_job

        user = User.objects.create_user(email='submit@test.com', password='x', credit_balance=5)
        job = TranslationJob.objects.create(
            user=user, source_video_key='translations/uploads/a.mp4', source_filename='clip.mp4',
            source_file_size_bytes=10, target_language='zh', song_title='Canción',
        )
        submit.return_value = {'remote_job_id': 'remote-9', 'status': 'queued', 'stage': 'en_cola',
                               'progress_pct': 0}

        process_translation_job(str(job.id))

        endpoint, body = submit.call_args.args
        self.assertEqual(endpoint, 'https://modal.test/translate')
        self.assertEqual(body, {
            's3_key': 'translations/uploads/a.mp4', 'client_job_id': str(job.id), 'target_language': 'zh',
            'title': 'Canción', 'artist': None, 'mode': 'simulated', 'sing': False, 'debug': False,
        })
        job.refresh_from_db()
        self.assertEqual(job.remote_job_id, 'remote-9')
        self.assertIsNotNone(job.started_at)
        schedule.assert_called_once_with(str(job.id), countdown=0)


@override_settings(
    TRANSLATION_CREDIT_COST=3,
    MODAL_ENDPOINT_TRANSLATE_VIDEO='https://modal.test/translate',
    TRANSLATION_REMOTE_TIMEOUT_SECONDS=2400,
)
class PollTranslationTests(TestCase):
    def setUp(self):
        from apps.credits.services.credit_service import reserve_credits

        self.user = User.objects.create_user(email='poll@test.com', password='x', credit_balance=5)
        self.job = TranslationJob.objects.create(
            user=self.user,
            source_video_key='translations/uploads/a.mp4',
            source_filename='clip.mp4',
            source_file_size_bytes=10,
            target_language='es',
            remote_job_id='remote-1',
            status='processing',
        )
        self.reservation = reserve_credits(
            self.user, amount=3, reference_id=str(self.job.id), reference_type='translation_job',
        )

    @patch('ml.storage_client.get_storage_bucket', return_value='musical-bucket')
    @patch('ml.storage_client.get_storage_client')
    @patch('ml.modal_client.get_translation_job_status')
    def test_completed_job_saves_results_and_charges_credits(self, status, get_client, _bucket):
        lyrics = {'idioma_origen': 'en', 'idioma_destino': 'es', 'frases': [{'inicio': 0, 'fin': 1, 'texto': 'Hola'}]}
        status.return_value = {
            'status': 'completed', 'progress_pct': 100, 'stage': 'completado', 'mode': 'simulated',
            'outputs': {'video': 'translations/r/resultado.mp4', 'audio': 'translations/r/voz.mp3',
                        'lyrics': 'translations/r/letra.json'},
            'details': {'modelo_llm': 'simulado'},
        }
        storage = get_client.return_value
        storage.head_object.return_value = {'ContentLength': 100}
        storage.get_object.return_value = {'Body': BytesIO(json.dumps(lyrics).encode())}

        poll_translation_job(str(self.job.id))

        self.job.refresh_from_db()
        self.user.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')
        self.assertEqual(self.job.result_video_key, 'translations/r/resultado.mp4')
        self.assertEqual(self.job.lyrics['frases'][0]['texto'], 'Hola')
        self.assertEqual(self.job.credits_used, 3)
        self.assertEqual(self.reservation.status, 'confirmed')
        self.assertEqual(self.user.credit_balance, 2)

    @patch('ml.modal_client.get_translation_job_status')
    def test_failed_job_releases_credits(self, status):
        status.return_value = {'status': 'failed', 'progress_pct': 40, 'error_message': 'Sin voz cantada'}

        poll_translation_job(str(self.job.id))

        self.job.refresh_from_db()
        self.reservation.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertEqual(self.job.error_message, 'Sin voz cantada')
        self.assertEqual(self.reservation.status, 'released')
        self.assertEqual(self.user.credit_balance, 5)

    @patch('apps.translations.tasks._schedule_poll')
    @patch('ml.modal_client.get_translation_job_status')
    def test_processing_job_updates_stage_and_keeps_polling(self, status, schedule):
        status.return_value = {'status': 'processing', 'progress_pct': 55, 'stage': 'traduciendo', 'mode': 'simulated'}

        poll_translation_job(str(self.job.id))

        self.job.refresh_from_db()
        self.assertEqual(self.job.stage, 'traduciendo')
        self.assertEqual(self.job.progress_pct, 55)
        schedule.assert_called_once_with(str(self.job.id))


class TranslationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='api@test.com', password='x', credit_balance=5)
        self.other = User.objects.create_user(email='otro@test.com', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_config_exposes_limits_and_languages(self):
        response = self.client.get('/api/translations/config/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['code'] for item in response.data['languages']}, {'en', 'es', 'fr', 'zh'})
        self.assertIn('credit_cost', response.data)

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get('/api/translations/jobs/').status_code, 401)

    def test_user_cannot_see_other_users_jobs(self):
        job = TranslationJob.objects.create(
            user=self.other, source_filename='x.mp4', source_file_size_bytes=1, target_language='es',
        )
        self.assertEqual(self.client.get('/api/translations/jobs/').data, [])
        self.assertEqual(self.client.get(f'/api/translations/jobs/{job.id}/').status_code, 404)

    def test_create_without_file_returns_400(self):
        response = self.client.post('/api/translations/', {'target_language': 'es'}, format='multipart')
        self.assertEqual(response.status_code, 400)

    @override_settings(TRANSLATION_CREDIT_COST=3)
    @patch('apps.translations.tasks.process_translation_job.delay')
    @patch('apps.translations.services.translation_service.upload_fileobj', return_value='k.mp4')
    @patch('apps.translations.services.translation_service.subprocess.run')
    def test_create_returns_201_or_402_without_credits(self, run, _upload, delay):
        run.return_value = _probe_output()
        ok = self.client.post('/api/translations/', {'file': _video(), 'target_language': 'en'}, format='multipart')
        self.assertEqual(ok.status_code, 201)
        self.assertTrue(TranslationJob.objects.filter(id=ok.data['job_id'], user=self.user).exists())

        poor = APIClient()
        poor.force_authenticate(self.other)
        denied = poor.post('/api/translations/', {'file': _video(), 'target_language': 'en'}, format='multipart')
        self.assertEqual(denied.status_code, 402)
        self.assertEqual(delay.call_count, 1)
