from django.test import TestCase

from apps.credits.models import CreditTransaction
from apps.karaoke.models import KaraokeTrack, UserKaraokeAccess
from apps.karaoke.services.karaoke_service import request_karaoke
from apps.karaoke.tasks import _charge_pending_accesses
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
