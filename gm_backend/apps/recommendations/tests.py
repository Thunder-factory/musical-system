from django.test import TestCase

from apps.recommendations.models import ListeningHistory, UserTasteProfile
from apps.recommendations.services.history_service import update_listening_history
from apps.songs.models import Song, Tag
from apps.users.models import User


class RecommendationProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='recommendations@example.com',
            password='test-password',
            full_name='Recommendation User',
        )
        self.genre = Tag.objects.create(name='lofi-test', category='genre')
        self.mood = Tag.objects.create(name='chill-test', category='mood')
        self.song = Song.objects.create(
            user=self.user,
            title='Canción para perfil',
            status='ready',
            audio_s3_key='songs/recommendations.wav',
        )
        self.song.tags.set([self.genre, self.mood])

    def test_play_updates_history_and_profile(self):
        update_listening_history(self.user, self.song, duration_seconds=37)

        self.assertEqual(
            ListeningHistory.objects.get(user=self.user, tag=self.genre).play_count,
            1,
        )
        self.assertEqual(
            ListeningHistory.objects.get(user=self.user, tag=self.genre).total_seconds,
            37,
        )

        profile = UserTasteProfile.objects.get(user=self.user)
        self.assertEqual(
            {tag['name'] for tag in profile.top_tags},
            {'lofi-test', 'chill-test'},
        )
        self.assertEqual([tag['name'] for tag in profile.top_genres], ['lofi-test'])
        self.assertEqual([tag['name'] for tag in profile.top_moods], ['chill-test'])

    def test_repeated_play_increments_without_losing_seconds(self):
        update_listening_history(self.user, self.song, duration_seconds=10)
        update_listening_history(self.user, self.song, duration_seconds=15)

        history = ListeningHistory.objects.get(user=self.user, tag=self.genre)
        self.assertEqual(history.play_count, 2)
        self.assertEqual(history.total_seconds, 25)
        self.assertEqual(UserTasteProfile.objects.filter(user=self.user).count(), 1)
