from unittest.mock import patch

from django.test import TestCase

from apps.credits.models import CreditReservation, CreditTransaction
from apps.credits.services.credit_service import confirm_reservation, release_reservation
from apps.songs.models import GenerationJob, Song
from apps.songs.tasks import _mark_generation_failed, poll_generation_job, process_generation_job
from apps.users.models import User


class GenerationIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='generation-idempotency@example.com',
            password='test-password',
            full_name='Generation Test',
        )
        self.user.credit_balance = 2
        self.user.save(update_fields=['credit_balance'])
        self.song = Song.objects.create(
            user=self.user,
            title='Prueba',
            description='Una canción de prueba',
            status='draft',
        )
        self.job = GenerationJob.objects.create(
            user=self.user,
            song=self.song,
            mode='from_description',
            status='queued',
        )
        CreditReservation.objects.create(
            user=self.user,
            amount=1,
            reference_id=self.job.id,
            reference_type='generation_job',
        )

    @patch('apps.songs.tasks.compute_lyrics_timestamps.delay')
    @patch('apps.songs.tasks.poll_generation_job.apply_async')
    @patch('ml.modal_client.get_music_job_status')
    @patch('ml.modal_client.submit_music_job')
    def test_retry_after_completion_does_not_call_modal_or_charge_again(
        self, submit_music, get_status, _poll, _lyrics
    ):
        submit_music.return_value = {'remote_job_id': 'remote-generation-1'}
        get_status.return_value = {
            'status': 'completed',
            'progress_pct': 100,
            's3_key': 'songs/generated.wav',
            'cover_image_s3_key': 'songs/generated.png',
            'lyrics': 'Una línea',
            'categories': [],
        }

        process_generation_job.run(str(self.job.id))
        self.job.refresh_from_db()
        self.assertEqual(self.job.remote_job_id, 'remote-generation-1')

        from apps.songs.tasks import poll_generation_job
        poll_generation_job.run(str(self.job.id))
        poll_generation_job.run(str(self.job.id))

        self.assertEqual(submit_music.call_count, 1)
        self.assertEqual(
            CreditTransaction.objects.filter(
                user=self.user, type='generation_job', reference_id=self.job.id
            ).count(),
            1,
        )

    @patch('apps.notifications.services.notify_user')
    def test_failed_generation_notifies_with_job_reference(self, notify):
        _mark_generation_failed(str(self.job.id), 'Modal no respondió.')

        notify.assert_called_once_with(
            self.user,
            type='song_failed',
            reference_id=str(self.job.id),
            title='No se pudo generar la canción',
            message='Falló la generación de "Prueba": Modal no respondió.',
            push_message='La generación de tu canción no pudo completarse.',
        )

    @patch('apps.songs.tasks.compute_lyrics_timestamps.delay')
    @patch('apps.songs.tasks.poll_generation_job.retry', side_effect=RuntimeError('retry'))
    @patch('apps.songs.tasks._save_categories', side_effect=RuntimeError('db failure'))
    @patch('ml.modal_client.get_music_job_status')
    @patch('ml.modal_client.submit_music_job')
    def test_remote_result_is_kept_when_finalization_fails(
        self, submit_music, get_status, _categories, _retry, _lyrics
    ):
        submit_music.return_value = {'remote_job_id': 'remote-generation-2'}
        get_status.return_value = {
            'status': 'completed',
            's3_key': 'songs/recover.wav',
            'cover_image_s3_key': 'songs/recover.png',
            'lyrics': '',
            'categories': [],
        }

        process_generation_job.run(str(self.job.id))
        with self.assertRaises(RuntimeError):
            poll_generation_job.run(str(self.job.id))

        self.job.refresh_from_db()
        self.assertEqual(self.job.remote_result['s3_key'], 'songs/recover.wav')
        get_status.reset_mock()

        # La recuperación consume el resultado persistido, no vuelve a Modal.
        _categories.side_effect = None
        process_generation_job.run(str(self.job.id))
        self.assertFalse(get_status.called)

    @patch('apps.songs.tasks.compute_lyrics_timestamps.delay')
    def test_confirmed_reservation_finishes_without_second_charge(self, _lyrics):
        reservation = CreditReservation.objects.get(reference_id=self.job.id)
        confirm_reservation(str(reservation.id))
        self.job.remote_result = {
            's3_key': 'songs/already-generated.wav',
            'cover_image_s3_key': 'songs/already-generated.png',
            'categories': [],
        }
        self.job.save(update_fields=['remote_result'])

        process_generation_job.run(str(self.job.id))

        self.job.refresh_from_db()
        self.song.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')
        self.assertEqual(self.song.status, 'ready')
        self.assertEqual(CreditTransaction.objects.filter(user=self.user).count(), 1)

    @patch('apps.songs.tasks.compute_lyrics_timestamps.delay')
    def test_released_reservation_never_publishes_remote_result(self, _lyrics):
        reservation = CreditReservation.objects.get(reference_id=self.job.id)
        release_reservation(str(reservation.id))
        self.job.remote_result = {
            's3_key': 'songs/released.wav',
            'cover_image_s3_key': 'songs/released.png',
            'categories': [],
        }
        self.job.save(update_fields=['remote_result'])

        process_generation_job.run(str(self.job.id))

        self.job.refresh_from_db()
        self.song.refresh_from_db()
        self.assertEqual(self.job.status, 'no_credits')
        self.assertEqual(self.song.status, 'no_credits')
