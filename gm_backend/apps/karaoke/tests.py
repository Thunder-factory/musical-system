import sys
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.credits.models import CreditTransaction
from apps.credits.services.credit_service import confirm_reservation, reserve_credits, release_reservation
from apps.karaoke.models import KaraokeTrack, UserKaraokeAccess
from apps.karaoke.services.karaoke_service import request_karaoke
from apps.karaoke.tasks import _charge_pending_accesses
from apps.karaoke.services.room_service import RoomError, create_room
from apps.karaoke.views import KaraokeStatusView
from apps.users.models import User
from apps.songs.models import Song


class KaraokeCreditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='karaoke@example.com',
            password='test-password',
            full_name='Usuario Karaoke',
        )
        self.user.credit_balance = 5
        self.user.save(update_fields=['credit_balance'])
        self.song = Song.objects.create(
            user=self.user,
            title='Canción lista',
            description='Canción de prueba',
            status='ready',
            audio_s3_key='songs/test.wav',
        )

    def test_generation_does_not_charge_before_task_succeeds(self):
        track, already_owned = request_karaoke(self.user, str(self.song.id))

        self.assertFalse(already_owned)
        self.user.refresh_from_db()
        self.assertEqual(self.user.credit_balance, 5)
        self.assertEqual(
            UserKaraokeAccess.objects.get(user=self.user, karaoke_track=track).credits_paid,
            0,
        )

    def test_pending_access_is_charged_only_once_after_success(self):
        track = KaraokeTrack.objects.create(song=self.song, status='ready')
        access = UserKaraokeAccess.objects.create(
            user=self.user,
            karaoke_track=track,
            credits_paid=0,
        )

        _charge_pending_accesses(str(track.id))
        _charge_pending_accesses(str(track.id))

        self.user.refresh_from_db()
        access.refresh_from_db()
        self.assertEqual(self.user.credit_balance, 3)
        self.assertEqual(access.credits_paid, 2)
        self.assertEqual(
            CreditTransaction.objects.filter(
                user=self.user,
                type='karaoke',
            ).count(),
            1,
        )

    def test_failed_karaoke_can_be_requested_again(self):
        failed_track = KaraokeTrack.objects.create(
            song=self.song,
            status='failed',
        )
        UserKaraokeAccess.objects.create(
            user=self.user,
            karaoke_track=failed_track,
            credits_paid=0,
        )

        track, already_owned = request_karaoke(self.user, str(self.song.id))

        self.assertFalse(already_owned)
        self.assertNotEqual(track.id, failed_track.id)
        self.assertEqual(track.status, 'queued')
        self.assertEqual(
            UserKaraokeAccess.objects.get(
                user=self.user,
                karaoke_track=track,
            ).credits_paid,
            0,
        )

    def test_confirmed_karaoke_reservation_is_not_charged_again(self):
        track = KaraokeTrack.objects.create(song=self.song, status='ready')
        access = UserKaraokeAccess.objects.create(
            user=self.user,
            karaoke_track=track,
            credits_paid=0,
        )
        reservation = reserve_credits(
            self.user, 2, str(track.id), 'karaoke_access'
        )
        confirm_reservation(str(reservation.id))

        _charge_pending_accesses(str(track.id))

        access.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(access.credits_paid, 2)
        self.assertEqual(self.user.credit_balance, 3)
        self.assertEqual(CreditTransaction.objects.filter(user=self.user).count(), 1)

    def test_released_karaoke_reservation_removes_pending_access(self):
        track = KaraokeTrack.objects.create(song=self.song, status='ready')
        access = UserKaraokeAccess.objects.create(
            user=self.user,
            karaoke_track=track,
            credits_paid=0,
        )
        reservation = reserve_credits(
            self.user, 2, str(track.id), 'karaoke_access'
        )
        release_reservation(str(reservation.id))

        _charge_pending_accesses(str(track.id))

        self.assertFalse(UserKaraokeAccess.objects.filter(id=access.id).exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.credit_balance, 5)

    def test_status_is_not_visible_to_another_user(self):
        track = KaraokeTrack.objects.create(song=self.song, status='ready')
        other = User.objects.create_user(
            email='other@example.com', password='test-password', full_name='Otro'
        )
        request = APIRequestFactory().get(f'/api/karaoke/{track.id}/status/')
        force_authenticate(request, user=other)
        response = KaraokeStatusView.as_view()(request, id=track.id)
        self.assertEqual(response.status_code, 404)

    def test_status_exposes_processing_stage_to_owner(self):
        track = KaraokeTrack.objects.create(
            song=self.song,
            status='processing',
            processing_stage='transcribing',
        )
        request = APIRequestFactory().get(f'/api/karaoke/{track.id}/status/')
        force_authenticate(request, user=self.user)

        response = KaraokeStatusView.as_view()(request, id=track.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'processing')
        self.assertEqual(response.data['processing_stage'], 'transcribing')

    def test_room_requires_paid_access_not_pending_access(self):
        track = KaraokeTrack.objects.create(
            song=self.song, status='ready', instrumental_s3_key='stems/no_vocals.wav'
        )
        UserKaraokeAccess.objects.create(
            user=self.user, karaoke_track=track, credits_paid=0,
        )
        with self.assertRaises(RoomError) as context:
            create_room(self.user, str(track.id))
        self.assertEqual(context.exception.status_code, 403)

    @patch('apps.karaoke.services.karaoke_service._enqueue_generation')
    def test_uploaded_song_uses_the_same_karaoke_flow(self, enqueue):
        uploaded = Song.objects.create(
            user=self.user,
            title='Audio externo',
            status='ready',
            source_type='uploaded',
            audio_s3_key='songs/uploads/audio.mp3',
            audio_duration=30,
        )

        with self.captureOnCommitCallbacks(execute=True):
            track, already_owned = request_karaoke(self.user, str(uploaded.id))

        self.assertFalse(already_owned)
        self.assertEqual(track.status, 'queued')
        enqueue.assert_called_once_with(str(track.id))

    def test_private_uploaded_song_is_not_accessible_to_another_user(self):
        other = User.objects.create_user(
            email='other-upload@example.com', password='test-password', full_name='Other'
        )
        uploaded = Song.objects.create(
            user=self.user,
            title='Privada',
            status='ready',
            source_type='uploaded',
            audio_s3_key='songs/uploads/private.mp3',
        )

        with self.assertRaises(Song.DoesNotExist):
            request_karaoke(other, str(uploaded.id))

    @patch('ml.modal_client.submit_stem_job', return_value={'remote_job_id': 'remote-1'})
    @patch('apps.karaoke.tasks.poll_karaoke_track.apply_async')
    def test_generation_submits_and_returns_without_blocking(self, schedule, submit):
        track = KaraokeTrack.objects.create(song=self.song, status='queued')

        from apps.karaoke.tasks import generate_karaoke_track
        generate_karaoke_track.run(str(track.id))

        track.refresh_from_db()
        self.assertEqual(track.remote_job_id, 'remote-1')
        submit.assert_called_once()
        schedule.assert_called_once_with(args=[str(track.id)], countdown=0)

    @override_settings(GEMINI_API_KEY='')
    @patch('apps.karaoke.tasks._charge_pending_accesses')
    @patch('apps.karaoke.tasks.download_file')
    @patch('apps.karaoke.tasks.shutil.which', return_value='/usr/bin/ffmpeg')
    @patch('ml.modal_client.get_stem_job_status')
    @patch.dict(
        sys.modules,
        {
            'whisper': SimpleNamespace(
                load_model=lambda _name: SimpleNamespace(
                    transcribe=lambda *_args, **_kwargs: {
                        'segments': [
                            {'start': 0, 'end': 1.5, 'text': ' primera línea '},
                            {'start': 1.5, 'end': 3, 'text': 'segunda línea'},
                        ]
                    }
                )
            )
        },
    )
    def test_generation_persists_real_processing_stages(self, get_status, _which, download, _charge):
        track = KaraokeTrack.objects.create(
            song=self.song,
            status='queued',
            processing_stage='queued',
            remote_job_id='remote-1',
        )
        get_status.return_value = {
            'status': 'completed',
            'stems': {
                'vocals': 'stems/remote-1/vocals.wav',
                'no_vocals': 'stems/remote-1/no_vocals.wav',
            },
        }

        from apps.karaoke.tasks import poll_karaoke_track

        with patch('apps.karaoke.tasks._save_processing_stage', wraps=__import__(
            'apps.karaoke.tasks', fromlist=['_save_processing_stage']
        )._save_processing_stage) as save_stage:
            poll_karaoke_track.run(str(track.id))

        track.refresh_from_db()
        self.assertEqual(track.status, 'ready')
        self.assertEqual(track.processing_stage, 'completed')
        self.assertEqual(track.lyrics_timestamps[0]['text'], 'primera línea')
        self.assertEqual(
            [call.args[1] for call in save_stage.call_args_list],
            ['separating', 'transcribing', 'synchronizing'],
        )
