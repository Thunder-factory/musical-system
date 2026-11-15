from django.test import TestCase

from apps.mix.models import MixClip
from apps.mix.services.audio_editor import apply_clip_effects
from apps.mix.services.mix_service import add_clip, reorder_clips
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
