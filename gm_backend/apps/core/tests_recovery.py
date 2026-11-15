from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.credits.models import CreditReservation
from apps.karaoke.models import KaraokeTrack, UserKaraokeAccess
from apps.mix.models import MixExport, MixProject
from apps.songs.models import GenerationJob, Song
from apps.stems.models import StemJob
from apps.users.models import User


class AbandonedOperationRecoveryTests(TestCase):
    def test_recovery_fails_stale_song_and_releases_expired_reservation(self):
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

        requeue.assert_not_called()
        reservation.refresh_from_db()
        job.refresh_from_db()
        song.refresh_from_db()
        self.assertEqual(reservation.status, 'released')
        self.assertEqual(job.status, 'failed')
        self.assertEqual(song.status, 'failed')
        self.assertEqual(result['songs'], 0)
        self.assertEqual(result['failed'], 1)

    def test_recovery_requeues_only_with_active_reservation(self):
        user = User.objects.create_user(
            email='active-recovery@example.com', password='test-password', full_name='Recovery'
        )
        song = Song.objects.create(user=user, title='Stale', status='processing')
        job = GenerationJob.objects.create(
            user=user, song=song, mode='from_description', status='processing'
        )
        old = timezone.now() - timedelta(hours=2)
        GenerationJob.objects.filter(id=job.id).update(started_at=old, updated_at=old)
        CreditReservation.objects.create(
            user=user, amount=1, reference_id=job.id,
            reference_type='generation_job',
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with patch('apps.songs.tasks.process_generation_job.delay') as requeue:
            from apps.core.tasks import recover_abandoned_operations
            result = recover_abandoned_operations.run()

        requeue.assert_called_once_with(str(job.id))
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(result['songs'], 1)

    def test_recovery_does_not_requeue_confirmed_job_twice(self):
        user = User.objects.create_user(
            email='confirmed-recovery@example.com', password='test-password', full_name='Recovery'
        )
        song = Song.objects.create(user=user, title='Stale', status='processing')
        job = GenerationJob.objects.create(
            user=user, song=song, mode='from_description', status='processing'
        )
        old = timezone.now() - timedelta(hours=2)
        GenerationJob.objects.filter(id=job.id).update(started_at=old, updated_at=old)
        CreditReservation.objects.create(
            user=user, amount=1, reference_id=job.id,
            reference_type='generation_job', status='confirmed',
        )

        with patch('apps.songs.tasks.process_generation_job.delay') as requeue:
            from apps.core.tasks import recover_abandoned_operations
            first = recover_abandoned_operations.run()
            second = recover_abandoned_operations.run()

        requeue.assert_called_once_with(str(job.id))
        self.assertEqual(first['songs'], 1)
        self.assertEqual(second['songs'], 0)

    @patch('ml.modal_client.get_stem_job_status', return_value={'status': 'processing'})
    @patch('apps.mix.tasks.render_mix.delay')
    @patch('apps.stems.tasks.recover_stem_job.delay')
    @patch('apps.karaoke.tasks.poll_karaoke_track.delay')
    @patch('apps.songs.tasks.process_generation_job.delay')
    def test_recovery_closes_all_domains_without_a_reservation(
        self, song_requeue, karaoke_requeue, stems_requeue, mix_requeue, remote_status
    ):
        user = User.objects.create_user(
            email='all-recovery@example.com', password='test-password', full_name='Recovery'
        )
        song = Song.objects.create(user=user, title='Stale', status='processing')
        generation = GenerationJob.objects.create(
            user=user, song=song, mode='from_description', status='processing'
        )
        karaoke = KaraokeTrack.objects.create(
            song=song, status='processing', remote_job_id='karaoke-remote'
        )
        stem = StemJob.objects.create(
            user=user, source_audio_url='songs/source.wav',
            source_filename='source.wav', source_file_size_bytes=10,
            status='processing', remote_job_id='stem-remote',
        )
        mix = MixProject.objects.create(user=user, title='Mix', status='processing')
        export = MixExport.objects.create(mix_project=mix, status='processing')
        old = timezone.now() - timedelta(hours=2)
        GenerationJob.objects.filter(id=generation.id).update(started_at=old, updated_at=old)
        KaraokeTrack.objects.filter(id=karaoke.id).update(updated_at=old)
        StemJob.objects.filter(id=stem.id).update(started_at=old, updated_at=old)
        MixExport.objects.filter(id=export.id).update(updated_at=old)

        from apps.core.tasks import recover_abandoned_operations
        result = recover_abandoned_operations.run()

        generation.refresh_from_db()
        karaoke.refresh_from_db()
        stem.refresh_from_db()
        export.refresh_from_db()
        self.assertEqual(generation.status, 'failed')
        self.assertEqual(karaoke.status, 'failed')
        self.assertEqual(stem.status, 'failed')
        self.assertEqual(export.status, 'failed')
        self.assertEqual(result['failed'], 4)
        song_requeue.assert_not_called()
        karaoke_requeue.assert_not_called()
        stems_requeue.assert_not_called()
        mix_requeue.assert_not_called()
        self.assertEqual(remote_status.call_count, 2)

    @patch('ml.modal_client.get_stem_job_status', return_value={'status': 'processing'})
    @patch('apps.karaoke.tasks.poll_karaoke_track.delay')
    def test_karaoke_recovery_uses_access_users_not_song_owner(
        self, poll, remote_status
    ):
        owner = User.objects.create_user(
            email='public-owner@example.com', password='test-password', full_name='Owner'
        )
        guest = User.objects.create_user(
            email='public-guest@example.com', password='test-password', full_name='Guest'
        )
        song = Song.objects.create(
            user=owner, title='Public song', status='ready', is_public=True
        )
        track = KaraokeTrack.objects.create(
            song=song, status='processing', remote_job_id='karaoke-public'
        )
        UserKaraokeAccess.objects.create(user=guest, karaoke_track=track, credits_paid=0)
        CreditReservation.objects.create(
            user=owner,
            amount=2,
            reference_id=track.id,
            reference_type='karaoke_access',
            status='released',
        )
        CreditReservation.objects.create(
            user=guest,
            amount=2,
            reference_id=track.id,
            reference_type='karaoke_access',
            status='confirmed',
        )
        old = timezone.now() - timedelta(hours=2)
        KaraokeTrack.objects.filter(id=track.id).update(updated_at=old)

        from apps.core.tasks import recover_abandoned_operations
        result = recover_abandoned_operations.run()

        track.refresh_from_db()
        self.assertEqual(track.status, 'queued')
        poll.assert_called_once_with(str(track.id))
        self.assertEqual(result['karaoke'], 1)
        self.assertEqual(result['failed'], 0)
        remote_status.assert_called_once()
