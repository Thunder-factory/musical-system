from unittest.mock import patch

from django.test import TestCase

from apps.credits.models import CreditReservation, CreditTransaction
from apps.credits.services.credit_service import confirm_reservation, release_reservation
from apps.songs.models import GenerationJob, Song
from apps.songs.tasks import process_generation_job
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
    @patch('ml.modal_client.call_modal_endpoint')
    def test_retry_after_completion_does_not_call_modal_or_charge_again(self, call_modal, _lyrics):
        call_modal.return_value = {
            's3_key': 'songs/generated.wav',
            'cover_image_s3_key': 'songs/generated.png',
            'lyrics': 'Una línea',
            'categories': [],
        }

        process_generation_job.run(str(self.job.id))
        process_generation_job.run(str(self.job.id))

        self.assertEqual(call_modal.call_count, 1)
        self.assertEqual(
            CreditTransaction.objects.filter(
                user=self.user, type='generation_job', reference_id=self.job.id
            ).count(),
            1,
        )

    @patch('apps.songs.tasks.compute_lyrics_timestamps.delay')
    @patch('apps.songs.tasks.process_generation_job.retry', side_effect=RuntimeError('retry'))
    @patch('apps.songs.tasks._save_categories', side_effect=RuntimeError('db failure'))
    @patch('ml.modal_client.call_modal_endpoint')
    def test_remote_result_is_kept_when_finalization_fails(self, call_modal, _categories, _retry, _lyrics):
        call_modal.return_value = {
            's3_key': 'songs/recover.wav',
            'cover_image_s3_key': 'songs/recover.png',
            'lyrics': '',
            'categories': [],
        }

        with self.assertRaises(RuntimeError):
            process_generation_job.run(str(self.job.id))

        self.job.refresh_from_db()
        self.assertEqual(self.job.remote_result['s3_key'], 'songs/recover.wav')
        call_modal.reset_mock()

        # La recuperación consume el resultado persistido, no vuelve a Modal.
        _categories.side_effect = None
        process_generation_job.run(str(self.job.id))
        self.assertFalse(call_modal.called)

    @patch('apps.songs.tasks.compute_lyrics_timestamps.delay')
    @patch('ml.modal_client.call_modal_endpoint')
    def test_confirmed_reservation_finishes_without_second_charge(self, call_modal, _lyrics):
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
        self.assertFalse(call_modal.called)
        self.assertEqual(CreditTransaction.objects.filter(user=self.user).count(), 1)

    @patch('apps.songs.tasks.compute_lyrics_timestamps.delay')
    @patch('ml.modal_client.call_modal_endpoint')
    def test_released_reservation_never_publishes_remote_result(self, call_modal, _lyrics):
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
        self.assertFalse(call_modal.called)
