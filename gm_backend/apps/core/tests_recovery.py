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

    def test_recovery_fails_stale_humming_enhancement_and_translation_and_releases_credits(self):
        from apps.humming.models import HummingEnhancement, HummingJob
        from apps.translations.models import TranslationJob

        user = User.objects.create_user(
            email='ht-recovery@example.com', password='test-password', full_name='HT Recovery'
        )
        user.credit_balance = 10
        user.save(update_fields=['credit_balance'])

        old = timezone.now() - timedelta(hours=2)

        h_job = HummingJob.objects.create(user=user, input_s3_key='humming/in.webm', status='processing')
        HummingJob.objects.filter(id=h_job.id).update(started_at=old, updated_at=old)
        h_res = CreditReservation.objects.create(
            user=user, amount=1, reference_id=h_job.id,
            reference_type='humming_job', expires_at=timezone.now() + timedelta(hours=1),
        )

        # Un tarareo reciente no debe tocarse
        fresh_h = HummingJob.objects.create(user=user, input_s3_key='humming/fresh.webm', status='queued')

        h_enh = HummingEnhancement.objects.create(
            humming_job=fresh_h, user=user, version_number=1,
            style_key='cumbia', style_label='Cumbia', prompt='cumbia',
            fidelity='media', ref_audio_strength=0.65, status='processing',
        )
        HummingEnhancement.objects.filter(id=h_enh.id).update(started_at=old, updated_at=old)
        e_res = CreditReservation.objects.create(
            user=user, amount=1, reference_id=h_enh.id,
            reference_type='humming_enhancement', expires_at=timezone.now() + timedelta(hours=1),
        )

        t_job = TranslationJob.objects.create(
            user=user, source_video_key='t/in.mp4', source_filename='in.mp4',
            source_file_size_bytes=100, target_language='en', status='processing',
        )
        TranslationJob.objects.filter(id=t_job.id).update(started_at=old, updated_at=old)
        t_res = CreditReservation.objects.create(
            user=user, amount=3, reference_id=t_job.id,
            reference_type='translation_job', expires_at=timezone.now() + timedelta(hours=1),
        )

        from apps.core.tasks import recover_abandoned_operations
        result = recover_abandoned_operations.run()

        for obj in (h_job, h_enh, t_job, h_res, e_res, t_res):
            obj.refresh_from_db()
        fresh_h.refresh_from_db()

        self.assertEqual(h_job.status, 'failed')
        self.assertEqual(h_enh.status, 'failed')
        self.assertEqual(t_job.status, 'failed')
        self.assertEqual(h_res.status, 'released')
        self.assertEqual(e_res.status, 'released')
        self.assertEqual(t_res.status, 'released')
        self.assertEqual(fresh_h.status, 'queued')
        self.assertEqual(result['humming'], 1)
        self.assertEqual(result['humming_enhancements'], 1)
        self.assertEqual(result['translations'], 1)
        self.assertEqual(result['reservations'], 3)

    def test_celery_beat_registers_recovery_every_10_minutes(self):
        from workers.celery import app

        schedule = app.conf.beat_schedule.get('recover-abandoned-operations-every-10m')
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule['task'], 'apps.core.tasks.recover_abandoned_operations')
        self.assertEqual(schedule['schedule'], 600.0)
