from django.test import TestCase

from apps.mix.models import MixClip
from apps.mix.models import MixExport
from apps.mix.tasks import _finalize_mix_export
from apps.mix.tasks import _discard_provisional_mix_song
from apps.mix.services.audio_editor import apply_clip_effects, compose_timeline
from apps.mix.services.mix_service import add_clip, reorder_clips
from apps.mix.services.mix_service import split_clip
from apps.credits.models import CreditReservation, CreditTransaction
from apps.songs.models import Song
from apps.users.models import User
from pydub import AudioSegment
from pydub.generators import Sine


class MixValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='mix@example.com', password='test-password', full_name='Mix User'
        )
        self.mix = self.user.mix_projects.create(title='Prueba')
        self.song = Song.objects.create(
            user=self.user,
            title='Audio listo',
            status='ready',
            audio_s3_key='songs/audio.wav',
            audio_duration=10,
        )

    def test_requires_exactly_one_accessible_ready_source(self):
        with self.assertRaisesMessage(ValueError, 'exactamente'):
            add_clip(
                self.mix, user=self.user, position=0, end_time_ms=1000,
            )
        with self.assertRaises(ValueError):
            add_clip(
                self.mix, user=self.user, position=0,
                song_id=str(self.song.id), stem_file_id='other', end_time_ms=1000,
            )

    def test_rejects_out_of_range_clip_and_invalid_fades(self):
        with self.assertRaises(ValueError):
            add_clip(
                self.mix, user=self.user, position=0,
                song_id=str(self.song.id), start_time_ms=0,
                end_time_ms=11000,
            )
        with self.assertRaises(ValueError):
            add_clip(
                self.mix, user=self.user, position=0,
                song_id=str(self.song.id), end_time_ms=1000,
                fade_in_ms=1001,
            )

    def test_reorder_requires_all_clips_exactly_once(self):
        first = add_clip(
            self.mix, user=self.user, position=0,
            song_id=str(self.song.id), end_time_ms=1000,
        )
        second = add_clip(
            self.mix, user=self.user, position=1,
            song_id=str(self.song.id), end_time_ms=1000,
        )
        with self.assertRaises(ValueError):
            reorder_clips(self.mix, [str(first.id)])
        reorder_clips(self.mix, [str(second.id), str(first.id)])
        self.assertEqual(
            list(MixClip.objects.filter(mix_project=self.mix).order_by('position').values_list('id', flat=True)),
            [second.id, first.id],
        )

    def test_volume_uses_logarithmic_decibels(self):
        clip = MixClip(
            mix_project=self.mix, start_time_ms=0, end_time_ms=1000,
            volume=0.5,
        )
        source = Sine(440).to_audio_segment(duration=1000).apply_gain(-10)
        result = apply_clip_effects(source, clip)
        self.assertAlmostEqual(result.dBFS - source.dBFS, -6.02, delta=0.2)

    def test_compose_timeline_preserves_gaps_and_overlaps(self):
        first = MixClip(
            mix_project=self.mix,
            timeline_start_ms=0,
            start_time_ms=0,
            end_time_ms=1000,
        )
        second = MixClip(
            mix_project=self.mix,
            timeline_start_ms=2000,
            start_time_ms=0,
            end_time_ms=1000,
        )
        first_audio = Sine(440).to_audio_segment(duration=1000)
        second_audio = Sine(660).to_audio_segment(duration=1000)

        result = compose_timeline([(first, first_audio), (second, second_audio)])

        self.assertEqual(len(result), 3000)
        self.assertTrue(result[1000:2000].dBFS == float('-inf'))

        second.timeline_start_ms = 500
        overlap = compose_timeline([(first, first_audio), (second, second_audio)])
        self.assertEqual(len(overlap), 1500)

    def test_mix_payment_and_publication_finalize_together(self):
        self.user.credit_balance = 3
        self.user.save(update_fields=['credit_balance'])
        export = MixExport.objects.create(mix_project=self.mix)
        song = Song.objects.create(
            user=self.user, title='Mix draft', status='draft',
            audio_s3_key='mix-exports/result.mp3',
        )
        CreditReservation.objects.create(
            user=self.user, amount=3, reference_id=export.id,
            reference_type='mix_export',
        )

        self.assertTrue(_finalize_mix_export(
            export.id, song.id, 'mix-exports/result.mp3', 10,
        ))
        export.refresh_from_db()
        song.refresh_from_db()
        self.mix.refresh_from_db()
        self.assertEqual(export.status, 'ready')
        self.assertEqual(song.status, 'ready')
        self.assertEqual(self.mix.status, 'ready')
        self.assertEqual(CreditTransaction.objects.filter(user=self.user).count(), 1)

    def test_mix_payment_failure_does_not_publish_draft_song(self):
        export = MixExport.objects.create(mix_project=self.mix)
        song = Song.objects.create(
            user=self.user, title='Mix draft', status='draft',
            audio_s3_key='mix-exports/failed.mp3',
        )
        CreditReservation.objects.create(
            user=self.user, amount=3, reference_id=export.id,
            reference_type='mix_export',
        )

        self.assertFalse(_finalize_mix_export(
            export.id, song.id, 'mix-exports/failed.mp3', 10,
        ))
        export.refresh_from_db()
        song.refresh_from_db()
        self.assertEqual(export.status, 'failed')
        self.assertEqual(song.status, 'draft')
        self.assertFalse(CreditTransaction.objects.filter(user=self.user).exists())

    def test_failed_finalization_removes_only_provisional_song(self):
        from unittest.mock import Mock

        song = Song.objects.create(
            user=self.user, title='Provisional', status='draft',
            audio_s3_key='mix-exports/provisional.mp3',
        )
        delete_file = Mock()

        _discard_provisional_mix_song(
            song.id, song.audio_s3_key, delete_file,
        )

        self.assertFalse(Song.objects.filter(id=song.id).exists())
        delete_file.assert_called_once_with('mix-exports/provisional.mp3')

    def test_split_preserves_mute_and_solo_state(self):
        clip = add_clip(
            self.mix, user=self.user, position=0,
            song_id=str(self.song.id), end_time_ms=4000,
            is_muted=True, is_solo=True,
        )

        left, right = split_clip(clip, user=self.user, playhead_ms=2000)

        self.assertTrue(left.is_muted)
        self.assertTrue(left.is_solo)
        self.assertTrue(right.is_muted)
        self.assertTrue(right.is_solo)
