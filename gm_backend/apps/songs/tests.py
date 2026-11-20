from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.songs.models import GenerationJob, Song
from apps.users.models import User


class GenerationJobListApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='jobs-user@example.com', password='test-password', full_name='Jobs User'
        )
        self.other = User.objects.create_user(
            email='jobs-other@example.com', password='test-password', full_name='Jobs Other'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_lists_latest_20_jobs_with_title_and_active_filter(self):
        other_song = Song.objects.create(user=self.other, title='Ajena', status='queued')
        GenerationJob.objects.create(user=self.other, song=other_song, mode='from_description', status='queued')

        now = timezone.now()
        for idx in range(22):
            song = Song.objects.create(user=self.user, title=f'Song {idx}', status='ready')
            job_status = 'processing' if idx == 21 else ('queued' if idx == 20 else 'completed')
            job = GenerationJob.objects.create(
                user=self.user, song=song, mode='from_description', status=job_status
            )
            GenerationJob.objects.filter(id=job.id).update(
                created_at=now - timedelta(minutes=25 - idx)
            )

        res_all = self.client.get('/api/songs/jobs/')
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(len(res_all.data), 20)
        self.assertEqual(res_all.data[0]['title'], 'Song 21')
        self.assertEqual(res_all.data[0]['song_title'], 'Song 21')
        self.assertEqual(res_all.data[0]['status'], 'processing')
        self.assertIn('created_at', res_all.data[0])
        self.assertIn('song_id', res_all.data[0])

        res_active = self.client.get('/api/songs/jobs/?active=1')
        self.assertEqual(res_active.status_code, 200)
        self.assertEqual([item['title'] for item in res_active.data], ['Song 21', 'Song 20'])


class SongLibraryApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='library-user@example.com', password='test-password', full_name='Library User'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_library_only_lists_ready_generated_songs(self):
        Song.objects.create(user=self.user, title='Lista', status='ready')
        Song.objects.create(user=self.user, title='Fallida', status='failed')
        Song.objects.create(user=self.user, title='En proceso', status='processing')
        Song.objects.create(user=self.user, title='Subida', status='ready', source_type='uploaded')

        response = self.client.get('/api/songs/library/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([song['title'] for song in response.data], ['Lista'])
