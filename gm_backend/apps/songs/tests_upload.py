from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.songs.models import GenerationJob, Song
from apps.songs.serializers import SongUpdateSerializer
from apps.songs.views import SongUploadView
from apps.users.models import User


class SongUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='uploader@example.com', password='test-password', full_name='Uploader'
        )
        self.factory = APIRequestFactory()

    def _file(self, name='my-song.mp3'):
        return SimpleUploadedFile(name, b'valid audio bytes', content_type='audio/mpeg')

    @patch('apps.songs.services.song_upload_service.validate_audio_file', return_value=('a' * 64, 42.5))
    @patch('apps.songs.services.song_upload_service.upload_fileobj', return_value='songs/uploads/user/song.mp3')
    def test_upload_creates_private_ready_song_without_job_or_charge(self, upload, _validate):
        request = self.factory.post('/api/songs/upload/', {'file': self._file(), 'title': 'Mi canción'}, format='multipart')
        force_authenticate(request, user=self.user)

        response = SongUploadView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        song = Song.objects.get()
        self.assertEqual(song.source_type, 'uploaded')
        self.assertEqual(song.status, 'ready')
        self.assertFalse(song.is_public)
        self.assertEqual(song.audio_duration, 42.5)
        self.assertFalse(GenerationJob.objects.exists())
        self.assertEqual(self.user.credit_balance, 0)
        upload.assert_called_once()

    def test_invalid_extension_is_rejected_before_r2(self):
        request = self.factory.post(
            '/api/songs/upload/', {'file': self._file('song.flac')}, format='multipart'
        )
        force_authenticate(request, user=self.user)

        with patch('apps.songs.services.song_upload_service.upload_fileobj') as upload:
            response = SongUploadView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        upload.assert_not_called()
        self.assertFalse(Song.objects.exists())

    @patch('apps.songs.services.song_upload_service.validate_audio_file', return_value=('a' * 64, 42.5))
    @patch('apps.songs.services.song_upload_service.upload_fileobj', return_value='songs/uploads/user/orphan.mp3')
    @patch('apps.songs.services.song_upload_service.delete_file')
    @patch('apps.songs.models.Song.objects.create', side_effect=RuntimeError('db down'))
    def test_database_failure_cleans_uploaded_object(self, _create, delete_file, upload, _validate):
        from apps.songs.services.song_upload_service import upload_song

        with self.assertRaisesRegex(RuntimeError, 'db down'):
            upload_song(self.user, self._file())

        delete_file.assert_called_once_with('songs/uploads/user/orphan.mp3')

    @patch('apps.songs.services.song_upload_service.validate_audio_file', return_value=('b' * 64, 42.5))
    @patch('apps.songs.services.song_upload_service.upload_fileobj', return_value='songs/uploads/user/duplicate.mp3')
    def test_identical_upload_is_idempotent(self, upload, _validate):
        from apps.songs.services.song_upload_service import upload_song

        first = upload_song(self.user, self._file())
        second = upload_song(self.user, self._file())

        self.assertEqual(first.id, second.id)
        self.assertEqual(Song.objects.count(), 1)
        upload.assert_called_once()

    @patch('apps.songs.services.song_upload_service.validate_audio_file', return_value=('c' * 64, 42.5))
    @patch('apps.songs.services.song_upload_service.upload_fileobj', return_value='songs/uploads/user/race.mp3')
    @patch('apps.songs.services.song_upload_service.delete_file')
    def test_duplicate_race_deletes_losing_r2_object(self, delete_file, upload, _validate):
        from django.db import IntegrityError
        from apps.songs.services.song_upload_service import upload_song

        existing = Song.objects.create(
            user=self.user,
            title='Ganadora',
            source_type='uploaded',
            source_sha256='c' * 64,
            audio_s3_key='songs/uploads/user/winner.mp3',
            status='ready',
        )
        empty = Song.objects.none()
        winner = Song.objects.filter(id=existing.id)
        with patch(
            'apps.songs.models.Song.objects.filter',
            side_effect=[empty, winner],
        ), patch(
            'apps.songs.models.Song.objects.create',
            side_effect=IntegrityError('duplicate'),
        ):
            result = upload_song(self.user, self._file())

        self.assertEqual(result.id, existing.id)
        delete_file.assert_called_once_with('songs/uploads/user/race.mp3')

    @patch('apps.songs.services.song_upload_service.validate_audio_file', return_value=('d' * 64, 42.5))
    @patch('apps.songs.services.song_upload_service.upload_fileobj', return_value='songs/uploads/user/reupload.mp3')
    def test_deleted_song_can_be_uploaded_again(self, upload, _validate):
        from django.utils import timezone
        from apps.songs.services.song_upload_service import upload_song

        deleted = upload_song(self.user, self._file())
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=['deleted_at'])

        replacement = upload_song(self.user, self._file())

        self.assertNotEqual(deleted.id, replacement.id)
        self.assertEqual(Song.objects.count(), 2)
        self.assertEqual(upload.call_count, 2)

    def test_uploaded_song_cannot_be_published(self):
        song = Song.objects.create(
            user=self.user,
            title='Privada',
            source_type='uploaded',
            source_sha256='e' * 64,
            audio_s3_key='songs/uploads/user/private.mp3',
            status='ready',
        )

        serializer = SongUpdateSerializer(song, data={'is_public': True}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn('is_public', serializer.errors)
