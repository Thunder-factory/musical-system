from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.credits.models import CreditReservation
from apps.songs.models import GenerationJob, Song
from apps.users.models import User


class AbandonedOperationRecoveryTests(TestCase):
    def test_recovery_requeues_stale_song_and_releases_expired_reservation(self):
        user = User.objects.create_user(
            email='recovery@example.com', password='test-password', full_name='Recovery'
        )
        user.credit_balance = 2
        user.save(update_fields=['credit_balance'])
        song = Song.objects.create(user=user, title='Stale', status='processing')
        job = GenerationJob.objects.create(
            user=user, song=song, mode='from_description', status='processing'
        )
        old = timezone.now() - timedelta(hours=2)
        GenerationJob.objects.filter(id=job.id).update(started_at=old)
        reservation = CreditReservation.objects.create(
            user=user, amount=1, reference_id=job.id,
            reference_type='generation_job', expires_at=old,
        )

        with patch('apps.songs.tasks.process_generation_job.delay') as requeue:
            from apps.core.tasks import recover_abandoned_operations
            result = recover_abandoned_operations.run()

        requeue.assert_called_once_with(str(job.id))
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'released')
        self.assertEqual(result['songs'], 1)
