import io
import json
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.credits.models import CreditReservation, CreditTransaction
from apps.credits.services.credit_service import release_reservation, reserve_credits
from apps.faceswap.models import FaceSwapJob, FaceSwapTemplate
from apps.faceswap.services.faceswap_service import (
    ActiveJobError,
    FaceSwapRequestError,
    InsufficientCreditsError,
    TemplateUnavailableError,
    request_face_swap,
)
from apps.faceswap.services.media_validation import (
    PhotoValidationError,
    VideoValidationError,
    validate_photo,
    validate_video,
)
from apps.users.models import User

SERVICE = 'apps.faceswap.services.faceswap_service'
TEMPLATE_SERVICE = 'apps.faceswap.services.template_service'


def _image_file(name='face.jpg', fmt='JPEG', size=(256, 256)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new('RGB', size, color=(200, 150, 120)).save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue())


def _video_file(name='clip.mp4') -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b'fake-video-bytes')


def _probe_output(duration: float, streams: bool = True) -> str:
    data = {'format': {'duration': str(duration)}}
    if streams:
        data['streams'] = [{'width': 720, 'height': 1280}]
    return json.dumps(data)


def _user(email: str, credits: int = 3, **extra) -> User:
    user = User.objects.create_user(
        email=email, password='test-password', full_name='Face Swap', **extra
    )
    user.credit_balance = credits
    user.save(update_fields=['credit_balance'])
    return user


def _template(**overrides) -> FaceSwapTemplate:
    values = {
        'title': 'Oficina — diario',
        'video_s3_key': 'faceswap/templates/videos/base.mp4',
        'thumbnail_s3_key': 'faceswap/templates/thumbnails/base.jpg',
        'duration_seconds': 8.4,
        'ref_time_s': 2.5,
    }
    values.update(overrides)
    return FaceSwapTemplate.objects.create(**values)


def _job(user, **overrides) -> FaceSwapJob:
    values = {
        'user': user,
        'source_type': 'upload',
        'photo_s3_key': 'faceswap/uploads/photos/p.jpg',
        'source_video_s3_key': 'faceswap/uploads/videos/v.mp4',
        'source_video_filename': 'clip.mp4',
        'status': 'processing',
        'remote_job_id': f'remote-{user.email}',
        'started_at': timezone.now(),
    }
    values.update(overrides)
    return FaceSwapJob.objects.create(**values)


class PhotoValidationTests(TestCase):
    def test_accepts_jpg_png_and_webp_and_restores_seek(self):
        for name, fmt in (('a.jpg', 'JPEG'), ('b.png', 'PNG'), ('c.webp', 'WEBP')):
            photo = _image_file(name, fmt)
            self.assertEqual(validate_photo(photo), Path(name).suffix)
            self.assertEqual(photo.tell(), 0)

    def test_rejects_gif(self):
        with self.assertRaisesRegex(PhotoValidationError, 'JPG, PNG o WEBP'):
            validate_photo(_image_file('a.gif', 'GIF'))

    def test_rejects_empty_file(self):
        with self.assertRaisesRegex(PhotoValidationError, 'vacía'):
            validate_photo(SimpleUploadedFile('a.jpg', b''))

    def test_rejects_corrupt_bytes(self):
        with self.assertRaisesRegex(PhotoValidationError, 'imagen válida'):
            validate_photo(SimpleUploadedFile('a.jpg', b'not-an-image'))

    @override_settings(FACESWAP_MAX_PHOTO_BYTES=100)
    def test_rejects_over_size_limit(self):
        with self.assertRaisesRegex(PhotoValidationError, 'excede'):
            validate_photo(_image_file())

    def test_rejects_small_image(self):
        with self.assertRaisesRegex(PhotoValidationError, '128'):
            validate_photo(_image_file(size=(64, 64)))


@patch('apps.faceswap.services.media_validation.subprocess.run')
class VideoValidationTests(TestCase):
    def test_accepts_ten_second_mp4(self, run):
        run.return_value.stdout = _probe_output(10)
        video = _video_file()
        self.assertEqual(validate_video(video, max_seconds=15), 10.0)
        self.assertEqual(video.tell(), 0)

    def test_rejects_avi(self, run):
        with self.assertRaisesRegex(VideoValidationError, 'MP4, MOV o WEBM'):
            validate_video(_video_file('clip.avi'), max_seconds=15)
        run.assert_not_called()

    def test_rejects_sixteen_seconds(self, run):
        run.return_value.stdout = _probe_output(16)
        with self.assertRaisesRegex(VideoValidationError, '15 segundos'):
            validate_video(_video_file(), max_seconds=15)

    def test_accepts_tolerance(self, run):
        run.return_value.stdout = _probe_output(15.4)
        self.assertEqual(validate_video(_video_file(), max_seconds=15), 15.4)

    def test_rejects_output_without_streams(self, run):
        run.return_value.stdout = _probe_output(5, streams=False)
        with self.assertRaisesRegex(VideoValidationError, 'decodificable'):
            validate_video(_video_file(), max_seconds=15)

    def test_rejects_ffprobe_error(self, run):
        run.side_effect = subprocess.CalledProcessError(1, 'ffprobe')
        with self.assertRaisesRegex(VideoValidationError, 'decodificable'):
            validate_video(_video_file(), max_seconds=15)

    @override_settings(FACESWAP_MAX_VIDEO_BYTES=4)
    def test_rejects_over_size_limit(self, run):
        with self.assertRaisesRegex(VideoValidationError, 'excede'):
            validate_video(_video_file(), max_seconds=15)
        run.assert_not_called()


@patch(f'{SERVICE}.process_faceswap_job.delay')
@patch(f'{SERVICE}.upload_fileobj', return_value='faceswap/uploads/photos/p.jpg')
@patch(f'{SERVICE}.validate_video', return_value=9.0)
@patch(f'{SERVICE}.validate_photo', return_value='.jpg')
class FaceSwapRequestTests(TestCase):
    def setUp(self):
        self.user = _user('fs-request@example.com')
        self.template = _template()

    def _request(self, **overrides):
        values = {
            'photo': _image_file(),
            'consent': 'true',
            'template_id': str(self.template.id),
            'video': None,
        }
        values.update(overrides)
        return request_face_swap(self.user, **values)

    def test_creates_queued_job_reservation_and_enqueues(self, _photo, _video, upload, delay):
        job = self._request()

        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.photo_s3_key, 'faceswap/uploads/photos/p.jpg')
        self.assertEqual(job.source_video_s3_key, self.template.video_s3_key)
        self.assertEqual(job.ref_time_s, 2.5)
        reservation = CreditReservation.objects.get(reference_id=job.id)
        self.assertEqual(
            (reservation.status, reservation.amount, reservation.reference_type),
            ('reserved', 3, 'faceswap_job'),
        )
        delay.assert_called_once_with(str(job.id))
        upload.assert_called_once()

    def test_without_credits_creates_nothing(self, *_mocks):
        self.user.credit_balance = 0
        self.user.save(update_fields=['credit_balance'])

        with self.assertRaises(InsufficientCreditsError):
            self._request()
        self.assertFalse(FaceSwapJob.objects.exists())
        self.assertFalse(CreditReservation.objects.exists())

    def test_active_job_returns_conflict(self, *_mocks):
        self.user.credit_balance = 6
        self.user.save(update_fields=['credit_balance'])
        self._request()
        with self.assertRaises(ActiveJobError):
            self._request()
        self.assertEqual(FaceSwapJob.objects.count(), 1)

    def test_abandoned_upload_is_failed_and_allows_new_job(self, *_mocks):
        stale = _job(self.user, status='queued', photo_s3_key=None, remote_job_id=None)
        old = timezone.now() - timedelta(hours=1)
        FaceSwapJob.objects.filter(id=stale.id).update(created_at=old)

        job = self._request()

        stale.refresh_from_db()
        self.assertEqual(stale.status, 'failed')
        self.assertEqual(stale.error_message, 'La subida quedó abandonada.')
        self.assertEqual(job.status, 'queued')

    def test_inactive_or_deleted_template_is_unavailable(self, *_mocks):
        inactive = _template(is_active=False)
        deleted = _template(deleted_at=timezone.now())
        for template in (inactive, deleted):
            with self.assertRaises(TemplateUnavailableError):
                self._request(template_id=str(template.id))
        with self.assertRaises(TemplateUnavailableError):
            self._request(template_id='not-a-uuid')

    def test_request_errors_before_touching_files(self, validate_photo_mock, *_mocks):
        cases = [
            {'photo': None},
            {'consent': 'false'},
            {'template_id': None},
            {'video': _video_file()},
        ]
        for overrides in cases:
            with self.assertRaises(FaceSwapRequestError):
                self._request(**overrides)
        validate_photo_mock.assert_not_called()

    def test_r2_failure_fails_job_and_releases(self, _photo, _video, upload, _delay):
        upload.side_effect = RuntimeError('R2 down')

        with self.assertRaisesRegex(RuntimeError, 'R2 down'):
            self._request()

        job = FaceSwapJob.objects.get(user=self.user)
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.error_message, 'No se pudo subir los archivos.')
        self.assertEqual(CreditReservation.objects.get(reference_id=job.id).status, 'released')

    @patch(f'{SERVICE}.delete_file')
    def test_enqueue_failure_deletes_uploaded_keys(
        self, delete_file, _photo, _video, upload, delay
    ):
        upload.side_effect = ['faceswap/uploads/photos/p.jpg', 'faceswap/uploads/videos/v.mp4']
        delay.side_effect = RuntimeError('Redis down')

        with self.assertRaisesRegex(RuntimeError, 'Redis down'):
            self._request(template_id=None, video=_video_file())

        deleted = [call.args[0] for call in delete_file.call_args_list]
        self.assertEqual(
            deleted, ['faceswap/uploads/photos/p.jpg', 'faceswap/uploads/videos/v.mp4']
        )
        job = FaceSwapJob.objects.get(user=self.user)
        self.assertEqual(job.status, 'failed')
        self.assertEqual(CreditReservation.objects.get(reference_id=job.id).status, 'released')


@patch(f'{SERVICE}.process_faceswap_job.delay')
@patch(f'{SERVICE}.upload_fileobj', return_value='faceswap/uploads/photos/p.jpg')
@patch(f'{SERVICE}.validate_video', return_value=9.0)
@patch(f'{SERVICE}.validate_photo', return_value='.jpg')
class FaceTargetSelectionTests(TestCase):
    """Personaje elegido: ref_time_s + face_x + face_y, todos o ninguno."""

    def setUp(self):
        self.user = _user('fs-target@example.com')
        self.template = _template()

    def _request(self, **overrides):
        values = {
            'photo': _image_file(),
            'consent': 'true',
            'template_id': str(self.template.id),
            'video': None,
        }
        values.update(overrides)
        return request_face_swap(self.user, **values)

    def test_partial_selection_is_rejected(self, validate_photo_mock, *_mocks):
        cases = [
            {'ref_time_s': '1.0'},
            {'face_x': '0.5', 'face_y': '0.5'},
            {'ref_time_s': '1.0', 'face_x': '0.5'},
            {'ref_time_s': '1.0', 'face_x': '0.5', 'face_y': ''},
        ]
        for overrides in cases:
            with self.assertRaisesMessage(
                FaceSwapRequestError,
                'Para elegir el personaje envía ref_time_s, face_x y face_y juntos.',
            ):
                self._request(**overrides)
        validate_photo_mock.assert_not_called()
        self.assertFalse(FaceSwapJob.objects.exists())

    def test_face_position_out_of_range_is_rejected(self, *_mocks):
        for x, y in (('-0.1', '0.5'), ('0.5', '1.2'), ('abc', '0.5'), ('nan', '0.5')):
            with self.assertRaisesMessage(
                FaceSwapRequestError, 'La posición de la cara debe estar entre 0 y 1.'
            ):
                self._request(ref_time_s='1.0', face_x=x, face_y=y)
        self.assertFalse(FaceSwapJob.objects.exists())

    def test_ref_time_outside_template_or_clip_is_rejected(self, *_mocks):
        cases = [
            {'ref_time_s': '8.5'},  # plantilla de 8.4 s
            {'ref_time_s': '-1'},
            {'ref_time_s': 'x'},
            {'ref_time_s': '9.5', 'template_id': None, 'video': _video_file()},  # clip de 9 s
        ]
        for overrides in cases:
            with self.assertRaisesMessage(
                FaceSwapRequestError, 'El momento elegido está fuera del video.'
            ):
                self._request(face_x='0.5', face_y='0.5', **overrides)
        self.assertFalse(FaceSwapJob.objects.exists())
        self.assertFalse(CreditReservation.objects.exists())

    def test_selection_is_saved_and_overrides_template_ref(self, *_mocks):
        job = self._request(ref_time_s='4.2', face_x='0.25', face_y='0.75')

        job.refresh_from_db()
        self.assertEqual(
            (job.ref_time_s, job.target_face_x, job.target_face_y), (4.2, 0.25, 0.75)
        )

    def test_selection_on_own_clip(self, *_mocks):
        job = self._request(
            template_id=None, video=_video_file(), ref_time_s='9', face_x='1', face_y='0'
        )

        job.refresh_from_db()
        self.assertEqual(
            (job.ref_time_s, job.target_face_x, job.target_face_y), (9.0, 1.0, 0.0)
        )

    def test_ref_time_is_capped_to_modal_limit(self, _photo, validate_video_mock, *_mocks):
        # Clip de 15.4 s: pasa la tolerancia de duración, pero Modal recorta a 15 s.
        validate_video_mock.return_value = 15.4
        job = self._request(
            template_id=None, video=_video_file(), ref_time_s='15.3', face_x='0.5', face_y='0.5'
        )

        job.refresh_from_db()
        self.assertEqual(job.ref_time_s, 15.0)

    def test_ref_time_rounding_past_end_is_capped_to_duration(self, *_mocks):
        job = self._request(ref_time_s='8.43', face_x='0.5', face_y='0.5')  # plantilla 8.4 s

        job.refresh_from_db()
        self.assertEqual(job.ref_time_s, 8.4)

    def test_without_selection_keeps_template_ref(self, *_mocks):
        job = self._request()

        job.refresh_from_db()
        self.assertEqual(job.ref_time_s, 2.5)
        self.assertIsNone(job.target_face_x)
        self.assertIsNone(job.target_face_y)


@patch('ml.storage_client.delete_file')
@patch('ml.storage_client.get_storage_bucket', return_value='musical-bucket')
@patch('ml.storage_client.get_storage_client')
@patch('apps.faceswap.tasks.poll_faceswap_job.apply_async')
class FaceSwapTaskTests(TestCase):
    def setUp(self):
        self.user = _user('fs-task@example.com')

    def _reserved_job(self, **overrides):
        job = _job(self.user, **overrides)
        reserve_credits(self.user, 3, str(job.id), 'faceswap_job')
        return job

    @patch('ml.modal_client.submit_faceswap_job', return_value={'remote_job_id': 'remote-new'})
    def test_submit_saves_remote_id_and_schedules_poll(self, submit, apply_async, *_mocks):
        from apps.faceswap.tasks import process_faceswap_job

        job = self._reserved_job(status='queued', remote_job_id=None, started_at=None)
        process_faceswap_job(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.remote_job_id, 'remote-new')
        self.assertIsNotNone(job.started_at)
        body = submit.call_args.args[1]
        self.assertEqual(body['client_job_id'], str(job.id))
        self.assertIsNone(body['face_x'])
        self.assertIsNone(body['face_y'])
        apply_async.assert_called_once_with(args=[str(job.id)], countdown=0)

        submit.reset_mock()
        process_faceswap_job(str(job.id))
        submit.assert_not_called()

    @patch('ml.modal_client.submit_faceswap_job', return_value={'remote_job_id': 'remote-pick'})
    def test_submit_sends_selected_face(self, submit, *_mocks):
        from apps.faceswap.tasks import process_faceswap_job

        job = self._reserved_job(
            status='queued', remote_job_id=None, started_at=None,
            ref_time_s=3.0, target_face_x=0.4, target_face_y=0.3,
        )
        process_faceswap_job(str(job.id))

        body = submit.call_args.args[1]
        self.assertEqual(
            (body['ref_time_s'], body['face_x'], body['face_y']), (3.0, 0.4, 0.3)
        )

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_poll_processing_updates_and_reschedules(self, status, apply_async, *_mocks):
        from apps.faceswap.tasks import poll_faceswap_job

        status.return_value = {'status': 'processing', 'progress_pct': 47}
        job = self._reserved_job()
        poll_faceswap_job(str(job.id))

        job.refresh_from_db()
        self.assertEqual((job.status, job.progress_pct), ('processing', 47))
        apply_async.assert_called_once_with(args=[str(job.id)], countdown=5)

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_poll_does_not_resurrect_job_failed_meanwhile(self, status, apply_async, *_mocks):
        from apps.faceswap.models import FaceSwapJob
        from apps.faceswap.tasks import poll_faceswap_job

        job = self._reserved_job()

        def fail_meanwhile(*_args):
            # La recuperación marca el job como fallido mientras se consulta Modal.
            FaceSwapJob.objects.filter(id=job.id).update(status='failed')
            return {'status': 'processing', 'progress_pct': 47}

        status.side_effect = fail_meanwhile
        poll_faceswap_job(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        apply_async.assert_not_called()

    def _completed(self, status, client, job):
        from apps.faceswap.tasks import poll_faceswap_job

        status.return_value = {
            'status': 'completed',
            'progress_pct': 100,
            'output_s3_key': f'faceswap/results/{job.remote_job_id}.mp4',
        }
        client.return_value.head_object.return_value = {'ContentLength': 2048}
        poll_faceswap_job(str(job.id))
        job.refresh_from_db()

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_poll_completed_charges_and_cleans_uploads(
        self, status, _apply, client, _bucket, delete_file
    ):
        job = self._reserved_job()
        self._completed(status, client, job)

        self.assertEqual((job.status, job.progress_pct, job.credits_used), ('completed', 100, 3))
        self.assertEqual(job.output_file_size_bytes, 2048)
        self.assertIsNone(job.photo_s3_key)
        self.assertIsNone(job.source_video_s3_key)
        deleted = {call.args[0] for call in delete_file.call_args_list}
        self.assertEqual(
            deleted, {'faceswap/uploads/photos/p.jpg', 'faceswap/uploads/videos/v.mp4'}
        )
        reservation = CreditReservation.objects.get(reference_id=job.id)
        self.assertEqual(reservation.status, 'confirmed')
        self.assertTrue(self.user.notifications.filter(type='faceswap_ready').exists())

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_poll_completed_keeps_template_video(
        self, status, _apply, client, _bucket, delete_file
    ):
        template = _template()
        job = self._reserved_job(
            source_type='template', template=template,
            source_video_s3_key=template.video_s3_key,
        )
        self._completed(status, client, job)

        deleted = [call.args[0] for call in delete_file.call_args_list]
        self.assertEqual(deleted, ['faceswap/uploads/photos/p.jpg'])
        self.assertEqual(job.source_video_s3_key, template.video_s3_key)

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_completed_poll_twice_charges_once(self, status, _apply, client, *_mocks):
        from apps.faceswap.tasks import poll_faceswap_job

        job = self._reserved_job()
        self._completed(status, client, job)
        poll_faceswap_job(str(job.id))

        self.user.refresh_from_db()
        self.assertEqual(CreditTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.user.credit_balance, 0)

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_invalid_or_empty_output_fails_and_releases(self, status, _apply, client, *_mocks):
        from apps.faceswap.tasks import poll_faceswap_job

        cases = [('outside/key.mp4', 100), ('faceswap/results/empty.mp4', 0)]
        for index, (key, length) in enumerate(cases):
            job = self._reserved_job(remote_job_id=f'remote-{index}')
            status.return_value = {'status': 'completed', 'progress_pct': 100, 'output_s3_key': key}
            client.return_value.head_object.return_value = {'ContentLength': length}
            poll_faceswap_job(str(job.id))

            job.refresh_from_db()
            self.assertEqual(job.status, 'failed')
            self.assertEqual(
                CreditReservation.objects.get(reference_id=job.id).status, 'released'
            )

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_remote_failure_releases_and_cleans(self, status, _apply, _client, _b, delete_file):
        from apps.faceswap.tasks import poll_faceswap_job

        status.return_value = {
            'status': 'failed', 'progress_pct': 0,
            'error_message': 'No se detectó una cara en la foto o en el video.',
        }
        job = self._reserved_job()
        poll_faceswap_job(str(job.id))

        job.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIn('cara', job.error_message)
        self.assertEqual(CreditReservation.objects.get(reference_id=job.id).status, 'released')
        self.assertEqual(delete_file.call_count, 2)
        self.assertEqual(self.user.credit_balance, 3)

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_timeout_fails_without_calling_modal(self, status, *_mocks):
        from apps.faceswap.tasks import poll_faceswap_job

        job = self._reserved_job(started_at=timezone.now() - timedelta(hours=1))
        poll_faceswap_job(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIn('tiempo máximo', job.error_message)
        status.assert_not_called()

    @patch('ml.modal_client.get_faceswap_job_status')
    def test_released_reservation_is_never_charged(self, status, _apply, client, *_mocks):
        job = self._reserved_job()
        release_reservation(str(CreditReservation.objects.get(reference_id=job.id).id))
        self._completed(status, client, job)

        self.assertEqual(job.status, 'failed')
        self.assertIn('liberada', job.error_message)
        self.assertFalse(CreditTransaction.objects.filter(user=self.user).exists())


@patch('apps.faceswap.serializers.generate_presigned_url', return_value='https://r2/signed')
class FaceSwapApiTests(TestCase):
    def setUp(self):
        self.user = _user('fs-api@example.com')
        self.other = _user('fs-other@example.com')
        self.admin = _user('fs-admin@example.com', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _as_admin(self):
        self.client.force_authenticate(self.admin)

    def test_templates_lists_only_active_and_not_deleted(self, _signed):
        active = _template(title='Activa')
        _template(title='Inactiva', is_active=False)
        _template(title='Borrada', deleted_at=timezone.now())

        response = self.client.get('/api/faceswap/templates/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.json()], [str(active.id)])
        self.assertTrue(response.json()[0]['has_reference'])
        self.assertEqual(response.json()[0]['preview_url'], 'https://r2/signed')

    def test_admin_endpoints_forbidden_for_regular_user(self, _signed):
        template = _template()
        self.assertEqual(self.client.get('/api/faceswap/admin/templates/').status_code, 403)
        self.assertEqual(self.client.post('/api/faceswap/admin/templates/', {}).status_code, 403)
        url = f'/api/faceswap/admin/templates/{template.id}/'
        self.assertEqual(self.client.patch(url, {}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)

    @patch(f'{TEMPLATE_SERVICE}.validate_video', return_value=8.0)
    def test_admin_create_rejects_ref_time_outside_video(self, _video, _signed):
        self._as_admin()
        response = self.client.post(
            '/api/faceswap/admin/templates/',
            {'title': 'Nueva', 'video': _video_file(), 'ref_time_s': '9'},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'El segundo de referencia está fuera del video.')

    @patch(f'{TEMPLATE_SERVICE}.upload_file')
    @patch(f'{TEMPLATE_SERVICE}.extract_thumbnail')
    @patch(f'{TEMPLATE_SERVICE}.upload_fileobj', return_value='faceswap/templates/videos/n.mp4')
    @patch(f'{TEMPLATE_SERVICE}.validate_video', return_value=8.0)
    def test_admin_create_update_and_delete(self, _video, _upload, extract, upload_file, _signed):
        thumb = Path(tempfile.mkstemp(suffix='.jpg')[1])
        extract.return_value = thumb
        self._as_admin()

        created = self.client.post(
            '/api/faceswap/admin/templates/',
            {'title': 'Nueva', 'video': _video_file(), 'ref_time_s': '2.5'},
            format='multipart',
        )
        self.assertEqual(created.status_code, 201, created.content)
        body = created.json()
        self.assertEqual((body['ref_time_s'], body['is_active']), (2.5, True))
        extract.assert_called_once()
        self.assertEqual(extract.call_args.args[1], 2.5)
        self.assertTrue(upload_file.call_args.args[1].startswith('faceswap/templates/thumbnails/'))
        self.assertFalse(thumb.exists())

        url = f"/api/faceswap/admin/templates/{body['id']}/"
        patched = self.client.patch(url, {'ref_time_s': '', 'is_active': 'false'})
        self.assertEqual(patched.status_code, 200, patched.content)
        self.assertEqual((patched.json()['ref_time_s'], patched.json()['is_active']), (None, False))

        listed = self.client.get('/api/faceswap/admin/templates/')
        self.assertEqual(len(listed.json()), 1)

        self.assertEqual(self.client.delete(url).status_code, 204)
        template = FaceSwapTemplate.objects.get(id=body['id'])
        self.assertIsNotNone(template.deleted_at)
        self.assertFalse(template.is_active)
        self.assertEqual(self.client.get('/api/faceswap/admin/templates/').json(), [])

    def test_create_job_without_photo_returns_400(self, _signed):
        response = self.client.post('/api/faceswap/jobs/', {'consent': 'true'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Debes subir una foto de tu cara.')

    @patch(f'{SERVICE}.validate_photo', return_value='.jpg')
    def test_create_job_without_credits_returns_402(self, _photo, _signed):
        self.user.credit_balance = 0
        self.user.save(update_fields=['credit_balance'])
        template = _template()
        response = self.client.post(
            '/api/faceswap/jobs/',
            {'photo': _image_file(), 'consent': 'true', 'template_id': str(template.id)},
            format='multipart',
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()['error'], 'Sin créditos suficientes.')

    @patch(f'{SERVICE}.delete_file')
    def test_delete_job_rules(self, delete_file, _signed):
        active = _job(self.user)
        url = f'/api/faceswap/jobs/{active.id}/'
        self.assertEqual(self.client.delete(url).status_code, 409)

        FaceSwapJob.objects.filter(id=active.id).update(
            status='completed', output_s3_key='faceswap/results/r.mp4'
        )
        self.assertEqual(self.client.delete(url).status_code, 204)
        active.refresh_from_db()
        self.assertIsNotNone(active.deleted_at)
        delete_file.assert_called_once_with('faceswap/results/r.mp4')
        self.assertEqual(self.client.get('/api/faceswap/jobs/').json(), [])
        self.assertEqual(self.client.get(url).status_code, 404)

    @patch(f'{SERVICE}.generate_presigned_url', return_value='https://r2/result')
    def test_result_url(self, presign, _signed):
        job = _job(self.user)
        url = f'/api/faceswap/jobs/{job.id}/result-url/'
        self.assertEqual(self.client.get(url).status_code, 409)

        FaceSwapJob.objects.filter(id=job.id).update(
            status='completed', output_s3_key='faceswap/results/r.mp4'
        )
        response = self.client.get(f'{url}?download=1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'url': 'https://r2/result'})
        kwargs = presign.call_args.kwargs
        self.assertEqual(kwargs['response_content_type'], 'video/mp4')
        self.assertEqual(
            kwargs['response_content_disposition'],
            f'attachment; filename="faceswap-{str(job.id)[:8]}.mp4"',
        )

    def test_other_users_job_is_not_found(self, _signed):
        job = _job(self.other, status='completed', output_s3_key='faceswap/results/x.mp4')
        base = f'/api/faceswap/jobs/{job.id}/'
        self.assertEqual(self.client.get(base).status_code, 404)
        self.assertEqual(self.client.delete(base).status_code, 404)
        self.assertEqual(self.client.get(f'{base}result-url/').status_code, 404)

    def test_job_payload_shape(self, _signed):
        template = _template()
        _job(
            self.user, source_type='template', template=template,
            source_video_filename=template.title,
        )
        item = self.client.get('/api/faceswap/jobs/').json()[0]
        self.assertEqual(item['template'], {'id': str(template.id), 'title': template.title})
        self.assertFalse(item['has_result'])
        self.assertNotIn('photo_s3_key', item)
        for field in ('ref_time_s', 'target_face_x', 'target_face_y'):
            self.assertIn(field, item)

    @patch(f'{SERVICE}.validate_photo', return_value='.jpg')
    def test_create_job_with_partial_selection_returns_400(self, _photo, _signed):
        template = _template()
        response = self.client.post('/api/faceswap/jobs/', {
            'photo': _image_file(), 'consent': 'true', 'template_id': str(template.id),
            'face_x': '0.5', 'face_y': '0.5',
        }, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            'error': 'Para elegir el personaje envía ref_time_s, face_x y face_y juntos.',
        })

    @patch(f'{SERVICE}.process_faceswap_job.delay')
    @patch(f'{SERVICE}.upload_fileobj', return_value='faceswap/uploads/photos/p.jpg')
    @patch(f'{SERVICE}.validate_photo', return_value='.jpg')
    def test_create_job_with_selection_saves_fields(self, _photo, _upload, _delay, _signed):
        template = _template()
        response = self.client.post('/api/faceswap/jobs/', {
            'photo': _image_file(), 'consent': 'true', 'template_id': str(template.id),
            'ref_time_s': '1.5', 'face_x': '0.6', 'face_y': '0.2',
        }, format='multipart')
        self.assertEqual(response.status_code, 201)
        item = self.client.get(f"/api/faceswap/jobs/{response.json()['job_id']}/").json()
        self.assertEqual(
            (item['ref_time_s'], item['target_face_x'], item['target_face_y']), (1.5, 0.6, 0.2)
        )


class FaceSwapRecoveryTests(TestCase):
    def setUp(self):
        self.user = _user('fs-recovery@example.com')

    def _stale_job(self):
        job = _job(self.user)
        old = timezone.now() - timedelta(hours=2)
        FaceSwapJob.objects.filter(id=job.id).update(started_at=old, updated_at=old)
        return job

    @patch('ml.modal_client.get_faceswap_job_status', return_value={'status': 'processing'})
    @patch('apps.faceswap.tasks.recover_faceswap_job.delay')
    def test_stale_job_with_valid_reservation_is_requeued(self, requeue, _status):
        from apps.core.tasks import recover_abandoned_operations

        job = self._stale_job()
        reserve_credits(self.user, 3, str(job.id), 'faceswap_job')

        result = recover_abandoned_operations.run()

        requeue.assert_called_once_with(str(job.id))
        self.assertEqual(result['faceswap'], 1)

    @patch('ml.storage_client.delete_file')
    @patch('ml.modal_client.get_faceswap_job_status', return_value={'status': 'processing'})
    @patch('apps.faceswap.tasks.recover_faceswap_job.delay')
    def test_stale_job_with_expired_reservation_fails(self, requeue, _status, delete_file):
        from apps.core.tasks import recover_abandoned_operations

        job = self._stale_job()
        CreditReservation.objects.create(
            user=self.user, amount=3, reference_id=job.id, reference_type='faceswap_job',
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        result = recover_abandoned_operations.run()

        job.refresh_from_db()
        requeue.assert_not_called()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(
            CreditReservation.objects.get(reference_id=job.id).status, 'released'
        )
        self.assertEqual(result['failed'], 1)
        self.assertEqual(delete_file.call_count, 2)
