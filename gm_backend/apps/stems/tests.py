from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.stems.services.stem_service import (
    AudioValidationError,
    validate_audio_file,
)
from apps.stems.tasks import _settle_stem_credits, _validate_stem_objects
from apps.users.models import User


class AudioValidationTests(TestCase):
    @patch('apps.stems.services.stem_service.subprocess.run')
    def test_accepts_mp3_and_restores_seek(self, run):
        run.return_value.stdout = '12.5\n'
        audio = SimpleUploadedFile('demo.mp3', b'not-real-audio')
        digest = validate_audio_file(audio, audio.name)

        self.assertEqual(audio.tell(), 0)
        self.assertEqual(len(digest), 64)
        run.assert_called_once()

    @patch('apps.stems.services.stem_service.subprocess.run')
    def test_accepts_wav(self, run):
        run.return_value.stdout = '2\n'
        audio = SimpleUploadedFile('demo.wav', b'RIFF' + b'0' * 20)
        validate_audio_file(audio, audio.name)
        self.assertEqual(audio.tell(), 0)

    def test_rejects_unsupported_extension(self):
        with self.assertRaises(AudioValidationError):
            validate_audio_file(SimpleUploadedFile('demo.flac', b'audio'), 'demo.flac')

    def test_rejects_empty_file(self):
        with self.assertRaises(AudioValidationError):
            validate_audio_file(SimpleUploadedFile('demo.mp3', b''), 'demo.mp3')

    @override_settings(STEM_MAX_DURATION_SECONDS=10)
    @patch('apps.stems.services.stem_service.subprocess.run')
    def test_rejects_duration_over_limit(self, run):
        run.return_value.stdout = '11\n'
        with self.assertRaises(AudioValidationError):
            validate_audio_file(SimpleUploadedFile('demo.mp3', b'audio'), 'demo.mp3')


class StemOutputValidationTests(TestCase):
    @patch('ml.storage_client.get_storage_bucket', return_value='musical-bucket')
    @patch('ml.storage_client.get_storage_client')
    def test_requires_both_non_empty_stems(self, get_client, _bucket):
        get_client.return_value.head_object.return_value = {'ContentLength': 12}
        _validate_stem_objects({
            'vocals': 'stems/job/vocals.wav',
            'no_vocals': 'stems/job/no_vocals.wav',
        })
        self.assertEqual(get_client.return_value.head_object.call_count, 2)

        with self.assertRaises(ValueError):
            _validate_stem_objects({'vocals': 'stems/job/vocals.wav'})

    @patch('ml.storage_client.get_storage_bucket', return_value='musical-bucket')
    @patch('ml.storage_client.get_storage_client')
    def test_r2_empty_object_is_rejected(self, get_client, _bucket):
        get_client.return_value.head_object.return_value = {'ContentLength': 0}
        with self.assertRaises(ValueError):
            _validate_stem_objects({
                'vocals': 'stems/job/vocals.wav',
                'no_vocals': 'stems/job/no_vocals.wav',
            })

    @patch('apps.notifications.services.notify_user')
    def test_failed_stem_notifies_with_job_reference(self, notify):
        from apps.stems.models import StemJob
        from apps.stems.tasks import _mark_stem_failed

        user = User.objects.create_user(
            email='stem-notification@example.com',
            password='test-password',
            full_name='Stem Notification',
        )
        job = StemJob.objects.create(
            user=user,
            source_audio_url='songs/source.wav',
            source_filename='source.wav',
            source_file_size_bytes=100,
        )

        _mark_stem_failed(str(job.id), 'Modal no devolvió vocals.')

        notify.assert_called_once_with(
            user,
            type='stem_failed',
            reference_id=str(job.id),
            title='No se pudieron separar las pistas',
            message='Falló la separación de pistas: Modal no devolvió vocals.',
            push_message='La separación de pistas no pudo completarse.',
        )


class StemUploadLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='stem-lifecycle@example.com',
            password='test-password',
            full_name='Stem Lifecycle',
        )
        self.user.credit_balance = 2
        self.user.save(update_fields=['credit_balance'])

    @patch('apps.stems.services.stem_service.validate_audio_file', return_value='a' * 64)
    @patch('apps.stems.services.stem_service.upload_fileobj', return_value='stems/demo.mp3')
    @patch('apps.stems.services.stem_service.process_stem_job.delay')
    def test_existing_active_job_is_returned_without_second_r2_upload(
        self, delay, upload, _validate
    ):
        from apps.stems.models import StemJob
        from apps.stems.services.stem_service import request_stem_separation

        first = request_stem_separation(
            self.user,
            SimpleUploadedFile('demo.mp3', b'audio'),
            'demo.mp3',
        )
        second = request_stem_separation(
            self.user,
            SimpleUploadedFile('demo.mp3', b'audio'),
            'demo.mp3',
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(upload.call_count, 1)
        self.assertEqual(StemJob.objects.filter(user=self.user).count(), 1)
        delay.assert_called_once()

    @patch('apps.stems.services.stem_service.validate_audio_file', return_value='b' * 64)
    @patch('apps.stems.services.stem_service.upload_fileobj', side_effect=RuntimeError('R2 down'))
    def test_r2_failure_releases_reservation_and_marks_job_failed(self, upload, _validate):
        from apps.credits.models import CreditReservation
        from apps.stems.models import StemJob
        from apps.stems.services.stem_service import request_stem_separation

        with self.assertRaisesRegex(RuntimeError, 'R2 down'):
            request_stem_separation(
                self.user,
                SimpleUploadedFile('demo.mp3', b'audio'),
                'demo.mp3',
            )

        self.assertEqual(
            CreditReservation.objects.filter(user=self.user, status='released').count(),
            1,
        )
        self.assertEqual(StemJob.objects.filter(user=self.user, status='failed').count(), 1)

    def test_confirmed_reservation_is_not_charged_again(self):
        from apps.credits.models import CreditReservation, CreditTransaction
        from apps.credits.services.credit_service import confirm_reservation, reserve_credits
        from apps.stems.models import StemJob

        job = StemJob.objects.create(
            user=self.user,
            source_audio_url='stems/source.wav',
            source_filename='source.wav',
            source_file_size_bytes=10,
            source_sha256='d' * 64,
            credits_used=0,
        )
        reservation = reserve_credits(self.user, 2, str(job.id), 'stem_job')
        confirm_reservation(str(reservation.id))

        _settle_stem_credits(job)
        self.assertEqual(CreditTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            CreditReservation.objects.get(id=reservation.id).status,
            'confirmed',
        )

    def test_released_reservation_never_falls_back_to_charge(self):
        from apps.credits.models import CreditReservation, CreditTransaction
        from apps.credits.services.credit_service import release_reservation, reserve_credits
        from apps.stems.models import StemJob

        job = StemJob.objects.create(
            user=self.user,
            source_audio_url='stems/source.wav',
            source_filename='source.wav',
            source_file_size_bytes=10,
            source_sha256='e' * 64,
            credits_used=0,
        )
        reservation = reserve_credits(self.user, 2, str(job.id), 'stem_job')
        release_reservation(str(reservation.id))

        with self.assertRaisesRegex(ValueError, 'liberada'):
            _settle_stem_credits(job)
        self.assertFalse(CreditTransaction.objects.filter(user=self.user).exists())

    @patch('apps.stems.services.stem_service.validate_audio_file', return_value='c' * 64)
    @patch('apps.stems.services.stem_service.delete_file')
    @patch('apps.stems.services.stem_service.process_stem_job.delay', side_effect=RuntimeError('Redis down'))
    @patch('apps.stems.services.stem_service.upload_fileobj', return_value='stems/orphan.wav')
    def test_enqueue_failure_deletes_uploaded_source(
        self, _upload, _delay, delete_file, _validate
    ):
        from apps.stems.models import StemJob
        from apps.stems.services.stem_service import request_stem_separation

        with self.assertRaisesRegex(RuntimeError, 'Redis down'):
            request_stem_separation(
                self.user,
                SimpleUploadedFile('demo.mp3', b'audio'),
                'demo.mp3',
            )

        delete_file.assert_called_once_with('stems/orphan.wav')
        self.assertEqual(StemJob.objects.filter(user=self.user, status='failed').count(), 1)


class StemFromSongTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.user = User.objects.create_user(
            email='stem-song@example.com',
            password='test-password',
            full_name='Stem Song',
        )
        self.user.credit_balance = 4
        self.user.save(update_fields=['credit_balance'])
        self.other = User.objects.create_user(
            email='stem-other@example.com',
            password='test-password',
            full_name='Other',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('apps.stems.services.stem_service.process_stem_job.delay')
    def test_separate_from_existing_song_creates_job_and_reserves_credits(self, delay):
        from apps.credits.models import CreditReservation
        from apps.songs.models import Song
        from apps.stems.models import StemJob

        song = Song.objects.create(
            user=self.user,
            title='Mi Rolita',
            status='ready',
            audio_s3_key='songs/generated/mi-rolita.wav',
        )

        res = self.client.post('/api/stems/separate/', {'song_id': str(song.id)}, format='json')
        self.assertEqual(res.status_code, 201, res.data)

        job = StemJob.objects.get(id=res.data['job_id'])
        self.assertEqual(job.source_audio_url, 'songs/generated/mi-rolita.wav')
        self.assertEqual(job.source_filename, 'Mi Rolita.wav')
        self.assertEqual(job.source_file_size_bytes, 0)
        self.assertTrue(
            CreditReservation.objects.filter(
                user=self.user, reference_id=job.id, reference_type='stem_job', status='reserved', amount=2
            ).exists()
        )
        delay.assert_called_once_with(str(job.id))

        # Idempotente si ya hay un job activo para esa canción
        res2 = self.client.post('/api/stems/separate/', {'song_id': str(song.id)}, format='json')
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.data['job_id'], str(job.id))
        self.assertEqual(StemJob.objects.count(), 1)

    def test_separate_from_song_errors_404_402_400(self):
        import uuid
        from apps.songs.models import Song

        # Sin parámetros -> 400
        self.assertEqual(self.client.post('/api/stems/separate/', {}, format='json').status_code, 400)

        # UUID inválido -> 400
        self.assertEqual(
            self.client.post('/api/stems/separate/', {'song_id': 'no-uuid'}, format='json').status_code,
            400,
        )

        # Canción ajena o inexistente -> 404
        foreign = Song.objects.create(
            user=self.other, title='Ajena', status='ready', audio_s3_key='songs/other.mp3'
        )
        self.assertEqual(
            self.client.post('/api/stems/separate/', {'song_id': str(foreign.id)}, format='json').status_code,
            404,
        )
        self.assertEqual(
            self.client.post('/api/stems/separate/', {'song_id': str(uuid.uuid4())}, format='json').status_code,
            404,
        )

        # Canción sin audio -> 400
        no_audio = Song.objects.create(user=self.user, title='Sin audio', status='ready', audio_s3_key='')
        self.assertEqual(
            self.client.post('/api/stems/separate/', {'song_id': str(no_audio.id)}, format='json').status_code,
            400,
        )

        # Sin créditos -> 402
        self.user.credit_balance = 1
        self.user.save(update_fields=['credit_balance'])
        ready = Song.objects.create(
            user=self.user, title='Lista', status='ready', audio_s3_key='songs/ok.mp3'
        )
        self.assertEqual(
            self.client.post('/api/stems/separate/', {'song_id': str(ready.id)}, format='json').status_code,
            402,
        )

    @patch('apps.stems.services.stem_service.delete_file')
    @patch('apps.stems.services.stem_service.process_stem_job.delay', side_effect=RuntimeError('Broker caído'))
    def test_enqueue_failure_from_song_never_deletes_song_audio(self, _delay, delete_file):
        from apps.credits.models import CreditReservation
        from apps.songs.models import Song
        from apps.stems.models import StemJob
        from apps.stems.services.stem_service import request_stem_separation_from_song

        song = Song.objects.create(
            user=self.user,
            title='Protegida',
            status='ready',
            audio_s3_key='songs/protected.mp3',
        )

        with self.assertRaisesRegex(RuntimeError, 'Broker caído'):
            request_stem_separation_from_song(self.user, str(song.id))

        delete_file.assert_not_called()
        self.assertEqual(StemJob.objects.filter(user=self.user, status='failed').count(), 1)
        self.assertEqual(CreditReservation.objects.filter(user=self.user, status='released').count(), 1)
