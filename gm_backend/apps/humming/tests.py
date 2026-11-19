import uuid
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.credits.models import CreditReservation
from apps.humming import services, tasks
from apps.humming.models import HummingJob
from apps.songs.models import Song
from apps.users.models import User

TOKEN = 'token-de-prueba'


def _response(status_code, json_data=None, headers=None, text=''):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.headers = headers or {}
    response.text = text
    return response


def _completed_payload(job_id, *, versions=(1, 2)):
    names = ['melodia.mid', 'analisis.json', 'partitura.musicxml']
    version_meta = []
    for number in versions:
        song = 'cancion.mp3' if number == 1 else f'cancion-{number}.mp3'
        arrangement = 'arreglo.mid' if number == 1 else f'arreglo-{number}.mid'
        names += [song, arrangement]
        version_meta.append({
            'numero': number, 'estilo': 'balada' if number == 1 else 'lofi',
            'variante': 'base', 'cancion': song, 'puntaje': 0.9, 'tipo': 'completa',
        })
    return {
        'jobId': str(job_id),
        'estado': 'COMPLETADO',
        'progreso': 100,
        'etapa': 'completado',
        'outputUrls': [f'https://r2.example/bucket/humming/x/{job_id}/salidas/{n}' for n in names],
        'error': None,
        'codigoError': None,
        'metadatos': {
            'bpm': 92.0, 'tonalidad': 'C major', 'acordes': ['C', 'G', 'Am', 'F'],
            'estilo': 'balada', 'estiloMensaje': 'Tu tarareo suena a balada.',
            'estiloAmbiguo': False, 'duracionCancionSegundos': 75.5,
            'versiones': version_meta,
        },
    }


@override_settings(
    TARAREO_CALLBACK_TOKEN=TOKEN,
    TARAREO_URL='http://tarareo:8000',
    TARAREO_CALLBACK_URL='http://backend:8000/api/humming/callback/',
    HUMMING_CREDIT_COST=1,
    HUMMING_MAX_DISPATCH_ATTEMPTS=3,
)
class HummingTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='tarareo@example.com', password='test-password', full_name='Tarareo'
        )
        self.user.credit_balance = 5
        self.user.save(update_fields=['credit_balance'])
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        storage = MagicMock()
        storage.generate_presigned_url.side_effect = (
            lambda op, Params, ExpiresIn: f"https://signed/{op}/{Params['Key']}"
        )
        patches = [
            patch('apps.humming.services.get_storage_client', return_value=storage),
            patch('apps.humming.services.get_storage_bucket', return_value='bucket'),
            patch('apps.humming.services.generate_presigned_url',
                  side_effect=lambda key, *a, **k: f'https://signed/get/{key}'),
            patch('apps.humming.serializers.generate_presigned_url',
                  side_effect=lambda key, *a, **k: f'https://signed/get/{key}'),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.storage = storage

    def _make_job(self, status='processing', attempts=1, reserve=True):
        job = HummingJob.objects.create(
            user=self.user, status=status, input_s3_key='humming/in.webm',
            dispatch_attempts=attempts,
        )
        job.output_keys = {name: services.output_key(job, name) for name in services.OUTPUT_CONTENT_TYPES}
        job.save()
        if reserve:
            services.reserve_credits(
                self.user, 1, reference_id=str(job.id), reference_type=services.RESERVATION_TYPE,
            )
        return job

    def _callback(self, payload, token=TOKEN):
        headers = {'HTTP_X_WORKER_TOKEN': token} if token is not None else {}
        return APIClient().post('/api/humming/callback/', payload, format='json', **headers)


class HummingUploadTests(HummingTestBase):
    def _file(self, name='tarareo.webm', content=b'audio-bytes'):
        return SimpleUploadedFile(name, content, content_type='audio/webm')

    @patch('apps.humming.tasks.dispatch_humming_job.delay')
    def test_upload_reserves_credit_uploads_and_schedules_dispatch(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/humming/', {'file': self._file(), 'title': 'Mi melodía'}, format='multipart'
            )

        self.assertEqual(response.status_code, 202, response.data)
        job = HummingJob.objects.get()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.title, 'Mi melodía')
        self.assertEqual(job.input_s3_key, f'humming/{self.user.id}/{job.id}/entrada.webm')
        self.storage.upload_fileobj.assert_called_once()
        self.assertTrue(CreditReservation.objects.filter(
            reference_id=str(job.id), status='reserved', amount=1).exists())
        delay.assert_called_once_with(str(job.id))

    def test_upload_without_credits_returns_402_and_leaves_nothing(self):
        self.user.credit_balance = 0
        self.user.save(update_fields=['credit_balance'])

        response = self.client.post('/api/humming/', {'file': self._file()}, format='multipart')

        self.assertEqual(response.status_code, 402)
        self.assertFalse(HummingJob.objects.exists())
        self.storage.upload_fileobj.assert_not_called()

    def test_upload_rejects_unknown_format(self):
        response = self.client.post(
            '/api/humming/', {'file': self._file('tarareo.exe')}, format='multipart'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(HummingJob.objects.exists())

    def test_r2_failure_releases_reservation_and_deletes_job(self):
        self.storage.upload_fileobj.side_effect = RuntimeError('r2 down')

        response = self.client.post('/api/humming/', {'file': self._file()}, format='multipart')

        self.assertEqual(response.status_code, 500)
        self.assertFalse(HummingJob.objects.exists())
        self.assertFalse(CreditReservation.objects.filter(status='reserved').exists())


class HummingDispatchTests(HummingTestBase):
    @patch('apps.humming.tasks.poll_humming_job.apply_async')
    @patch('apps.humming.services.requests.post', return_value=_response(202))
    def test_accepted_dispatch_marks_processing_and_starts_polling(self, post, poll):
        job = self._make_job(status='queued', attempts=0)

        tasks.dispatch_humming_job.apply(args=[str(job.id)])

        job.refresh_from_db()
        self.assertEqual(job.status, 'processing')
        self.assertEqual(job.dispatch_attempts, 1)
        self.assertEqual(set(job.output_keys), set(services.OUTPUT_CONTENT_TYPES))
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['jobId'], str(job.id))
        self.assertEqual(payload['version'], 1)
        self.assertEqual(payload['operacion'], 'generar')
        self.assertEqual(payload['callbackUrl'], 'http://backend:8000/api/humming/callback/')
        self.assertEqual(payload['inputUrls'], ['https://signed/get/humming/in.webm'])
        self.assertEqual(set(payload['outputUploadUrls']), set(services.OUTPUT_CONTENT_TYPES))
        # Cada PUT se firma con el Content-Type que espera el worker.
        signed = {c.kwargs['Params']['Key'].rsplit('/', 1)[1]: c.kwargs['Params']['ContentType']
                  for c in self.storage.generate_presigned_url.call_args_list}
        self.assertEqual(signed, services.OUTPUT_CONTENT_TYPES)
        poll.assert_called_once()
        self.assertEqual(poll.call_args.kwargs['args'], [str(job.id), 1])

    @patch('apps.humming.tasks.dispatch_humming_job.apply_async')
    @patch('apps.humming.services.requests.post',
           return_value=_response(503, headers={'Retry-After': '42'}))
    def test_busy_worker_reschedules_without_spending_attempts(self, _post, redispatch):
        job = self._make_job(status='queued', attempts=0)

        tasks.dispatch_humming_job.apply(args=[str(job.id)])

        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.dispatch_attempts, 0)
        redispatch.assert_called_once_with(args=[str(job.id)], countdown=42)

    @patch('apps.humming.services.requests.post', return_value=_response(422, text='bad'))
    def test_rejected_request_fails_and_releases_credits(self, _post):
        job = self._make_job(status='queued', attempts=0)

        tasks.dispatch_humming_job.apply(args=[str(job.id)])

        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.error_code, 'SOLICITUD_INVALIDA')
        self.assertEqual(CreditReservation.objects.get().status, 'released')


class HummingCallbackTests(HummingTestBase):
    def test_callback_requires_valid_token(self):
        job = self._make_job()
        payload = {'jobId': str(job.id), 'estado': 'PROCESANDO', 'progreso': 50}

        self.assertEqual(self._callback(payload, token='otro').status_code, 403)
        self.assertEqual(self._callback(payload, token=None).status_code, 403)
        with override_settings(TARAREO_CALLBACK_TOKEN=''):
            self.assertEqual(self._callback(payload, token='').status_code, 403)
        job.refresh_from_db()
        self.assertEqual(job.progress, 0)

    def test_unknown_job_returns_404(self):
        response = self._callback({'jobId': str(uuid.uuid4()), 'estado': 'PROCESANDO'})
        self.assertEqual(response.status_code, 404)

    def test_progress_callback_updates_stage_and_outputs(self):
        job = self._make_job()
        payload = {
            'jobId': str(job.id), 'estado': 'PROCESANDO', 'progreso': 70, 'etapa': 'version-1-lista',
            'outputUrls': [f'https://r2.example/b/humming/x/{job.id}/salidas/cancion.mp3'],
        }

        self.assertEqual(self._callback(payload).status_code, 204)

        job.refresh_from_db()
        self.assertEqual(job.status, 'processing')
        self.assertEqual(job.progress, 70)
        self.assertEqual(job.stage, 'version-1-lista')
        self.assertEqual(job.available_outputs, ['cancion.mp3'])

    def test_completed_callback_charges_once_and_is_idempotent(self):
        job = self._make_job()
        payload = _completed_payload(job.id)

        self.assertEqual(self._callback(payload).status_code, 204)
        self.assertEqual(self._callback(payload).status_code, 204)

        job.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.credits_used, 1)
        self.assertEqual(job.metadata['estilo'], 'balada')
        self.assertIn('partitura.musicxml', job.available_outputs)
        self.assertEqual(self.user.credit_balance, 4)
        self.assertEqual(CreditReservation.objects.get().status, 'confirmed')

    def test_invalid_input_fails_without_retry_and_releases_credits(self):
        job = self._make_job()
        payload = {
            'jobId': str(job.id), 'estado': 'FALLIDO', 'progreso': 100, 'etapa': 'preprocesado',
            'error': 'Probá tararear más fuerte.', 'codigoError': 'ENTRADA_INVALIDA',
            'metadatos': {'motivo': 'SIN_SENAL'},
        }

        with patch('apps.humming.tasks.dispatch_humming_job.apply_async') as redispatch:
            self.assertEqual(self._callback(payload).status_code, 204)

        job.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.error_code, 'ENTRADA_INVALIDA')
        self.assertEqual(job.error_message, 'Probá tararear más fuerte.')
        self.assertEqual(self.user.credit_balance, 5)
        self.assertEqual(CreditReservation.objects.get().status, 'released')
        redispatch.assert_not_called()

    def test_internal_error_requeues_while_attempts_remain(self):
        job = self._make_job(attempts=1)
        payload = {
            'jobId': str(job.id), 'estado': 'FALLIDO', 'progreso': 100,
            'error': 'R2 no respondió', 'codigoError': 'ERROR_INTERNO',
        }

        with patch('apps.humming.tasks.dispatch_humming_job.apply_async') as redispatch:
            self._callback(payload)

        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        redispatch.assert_called_once()

    def test_internal_error_fails_when_attempts_are_exhausted(self):
        job = self._make_job(attempts=3)
        payload = {
            'jobId': str(job.id), 'estado': 'FALLIDO', 'progreso': 100,
            'error': 'R2 no respondió', 'codigoError': 'ERROR_INTERNO',
        }

        with patch('apps.humming.tasks.dispatch_humming_job.apply_async') as redispatch:
            self._callback(payload)

        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.error_code, 'ERROR_INTERNO')
        redispatch.assert_not_called()
        self.assertEqual(CreditReservation.objects.get().status, 'released')


class HummingPollingTests(HummingTestBase):
    def _stale_heartbeat(self, job):
        HummingJob.objects.filter(id=job.id).update(last_heartbeat_at=None)

    @patch('apps.humming.services.requests.get')
    def test_poll_from_previous_dispatch_is_ignored(self, get):
        job = self._make_job(attempts=2)

        tasks.poll_humming_job.apply(args=[str(job.id), 1])

        get.assert_not_called()

    @patch('apps.humming.tasks.dispatch_humming_job.apply_async')
    @patch('apps.humming.services.requests.get', return_value=_response(404))
    def test_poll_redispatches_job_lost_by_worker(self, _get, redispatch):
        job = self._make_job(attempts=1)
        self._stale_heartbeat(job)

        tasks.poll_humming_job.apply(args=[str(job.id), 1])

        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        redispatch.assert_called_once()

    @patch('apps.humming.tasks.poll_humming_job.apply_async')
    @patch('apps.humming.services.requests.get')
    def test_poll_applies_completed_result(self, get, poll):
        job = self._make_job(attempts=1)
        self._stale_heartbeat(job)
        get.return_value = _response(200, _completed_payload(job.id))

        tasks.poll_humming_job.apply(args=[str(job.id), 1])

        job.refresh_from_db()
        self.assertEqual(job.status, 'completed')
        poll.assert_not_called()


class HummingChooseTests(HummingTestBase):
    def _completed_job(self):
        job = self._make_job()
        services.apply_worker_result(str(job.id), _completed_payload(job.id))
        job.refresh_from_db()
        return job

    def test_detail_lists_ready_versions_with_signed_urls(self):
        job = self._completed_job()

        response = self.client.get(f'/api/humming/{job.id}/')

        self.assertEqual(response.status_code, 200)
        versions = response.data['versions']
        self.assertEqual([v['number'] for v in versions], [1, 2])
        self.assertEqual(versions[1]['style'], 'lofi')
        self.assertTrue(versions[1]['audio_url'].endswith('/salidas/cancion-2.mp3'))
        self.assertIsNotNone(response.data['downloads']['score_musicxml_url'])
        self.assertEqual(response.data['metadata']['tonalidad'], 'C major')

    def test_other_users_cannot_see_the_job(self):
        job = self._completed_job()
        other = User.objects.create_user(email='otro@example.com', password='x', full_name='Otro')
        client = APIClient()
        client.force_authenticate(other)

        self.assertEqual(client.get(f'/api/humming/{job.id}/').status_code, 404)
        self.assertEqual(
            client.post(f'/api/humming/{job.id}/choose/', {'version': 1}, format='json').status_code,
            404,
        )

    def test_choose_creates_hummed_song_once(self):
        job = self._completed_job()

        first = self.client.post(
            f'/api/humming/{job.id}/choose/', {'version': 2, 'title': 'Lo-fi del bus'}, format='json'
        )
        again = self.client.post(f'/api/humming/{job.id}/choose/', {'version': 2}, format='json')
        other = self.client.post(f'/api/humming/{job.id}/choose/', {'version': 1}, format='json')

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(again.status_code, 201)
        self.assertEqual(other.status_code, 409)
        song = Song.objects.get()
        self.assertEqual(song.source_type, 'hummed')
        self.assertEqual(song.title, 'Lo-fi del bus')
        self.assertEqual(song.status, 'ready')
        self.assertTrue(song.instrumental)
        self.assertEqual(song.audio_s3_key, job.output_keys['cancion-2.mp3'])
        self.assertEqual(list(song.tags.values_list('name', flat=True)), ['lofi'])
        job.refresh_from_db()
        self.assertEqual(job.chosen_version, 2)
        self.assertEqual(job.song_id, song.id)

    def test_cannot_choose_before_completion(self):
        job = self._make_job()

        response = self.client.post(f'/api/humming/{job.id}/choose/', {'version': 1}, format='json')

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Song.objects.exists())
