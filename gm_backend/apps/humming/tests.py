import uuid
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.credits.models import CreditReservation
from apps.humming import enhancement as enhancement_service
from apps.humming import services, tasks
from apps.humming.models import HummingEnhancement, HummingJob
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

    @patch('apps.humming.tasks.warm_ai_gpu.delay')
    @patch('apps.humming.tasks.dispatch_humming_job.delay')
    def test_upload_reserves_credit_uploads_and_schedules_dispatch(self, delay, _warm):
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

    def test_malformed_job_id_returns_404_not_500(self):
        for job_id in ('no-es-uuid', None, 123):
            response = self._callback({'jobId': job_id, 'estado': 'PROCESANDO'})
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


class HummingProgressiveVersionsTests(HummingTestBase):
    ANALISIS = {
        'analisis': {'bpm': 64.0, 'tonalidad': 'Bb minor'},
        'armonia': {'acordes': ['Bbm', 'Ebm']},
        'estilo': {'preset': 'lofi', 'mensaje': 'Tu tarareo suena a lo-fi.', 'ambiguo': False},
        'render': {'duracionSegundos': 91.6},
        'versiones': [{'numero': 1, 'estilo': 'lofi', 'variante': 'base', 'cancion': 'cancion.mp3',
                       'puntaje': 0.9, 'tipo': 'completa'}],
    }

    def _download(self, key, buffer):
        import json as _json

        buffer.write(_json.dumps(self.ANALISIS).encode('utf-8'))

    def test_first_version_is_listed_before_the_job_completes(self):
        job = self._make_job()
        urls = [f'https://r2.example/b/humming/x/{job.id}/salidas/{n}'
                for n in ('cancion.mp3', 'arreglo.mid', 'melodia.mid', 'analisis.json')]
        payload = {'jobId': str(job.id), 'estado': 'PROCESANDO', 'progreso': 70,
                   'etapa': 'version-1-lista', 'outputUrls': urls}

        with patch('apps.humming.services.download_fileobj', side_effect=self._download):
            self.assertEqual(self._callback(payload).status_code, 204)

        job.refresh_from_db()
        self.assertEqual(job.status, 'processing')
        self.assertTrue(job.metadata['provisional'])
        detail = self.client.get(f'/api/humming/{job.id}/').data
        self.assertEqual(detail['status'], 'processing')
        self.assertEqual([v['style'] for v in detail['versions']], ['lofi'])
        self.assertEqual(detail['metadata']['tonalidad'], 'Bb minor')

    def test_chart_data_from_the_analysis_is_public(self):
        grafico = {'pasoSegundos': 0.05, 'contorno': [60.1, None, 62.0],
                   'notas': [[60, 0.0, 0.5]], 'cancion': [[60, 0.02, 0.47]]}
        metadata = services.metadata_from_analysis({**self.ANALISIS, 'grafico': grafico})
        job = self._make_job()
        HummingJob.objects.filter(id=job.id).update(metadata=metadata)

        detail = self.client.get(f'/api/humming/{job.id}/').data

        self.assertEqual(detail['metadata']['grafico'], grafico)

    def test_plain_progress_does_not_download_the_analysis(self):
        job = self._make_job()
        payload = {'jobId': str(job.id), 'estado': 'PROCESANDO', 'progreso': 40, 'etapa': 'analisis'}

        with patch('apps.humming.services.download_fileobj') as download:
            self._callback(payload)

        download.assert_not_called()


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

    def test_chosen_song_appears_in_library(self):
        job = self._completed_job()
        self.client.post(f'/api/humming/{job.id}/choose/', {'version': 1}, format='json')

        response = self.client.get('/api/songs/library/')

        self.assertEqual(response.status_code, 200)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual([item['source_type'] for item in items], ['hummed'])

    def test_cannot_choose_before_completion(self):
        job = self._make_job()

        response = self.client.post(f'/api/humming/{job.id}/choose/', {'version': 1}, format='json')

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Song.objects.exists())


@override_settings(
    MODAL_ENDPOINT_FROM_REFERENCE='https://modal.example/from-reference',
    HUMMING_ENHANCE_CREDIT_COST=1,
)
class HummingEnhancementTests(HummingTestBase):
    def _completed_job(self):
        job = self._make_job()
        services.apply_worker_result(str(job.id), _completed_payload(job.id))
        job.refresh_from_db()
        return job

    def _enhance(self, job, **body):
        payload = {'version': 1, 'style': 'cumbia', **body}
        with patch('apps.humming.tasks.submit_humming_enhancement.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(f'/api/humming/{job.id}/enhance/', payload, format='json')
        return response, delay

    def test_styles_catalog_lists_regional_styles(self):
        response = self.client.get('/api/humming/styles/')

        self.assertEqual(response.status_code, 200)
        keys = {style['key'] for style in response.data['styles']}
        self.assertTrue({'cumbia', 'huayno', 'morenada', 'jazz'} <= keys)
        self.assertTrue(response.data['available'])

    def test_enhance_reserves_credits_and_builds_prompt_with_bpm_and_key(self):
        job = self._completed_job()

        response, delay = self._enhance(job, version=2, fidelity='alta')

        self.assertEqual(response.status_code, 202, response.data)
        enhancement = HummingEnhancement.objects.get()
        self.assertEqual(enhancement.version_number, 2)
        self.assertEqual(enhancement.ref_audio_strength, 0.8)
        self.assertIn('cumbia', enhancement.prompt)
        self.assertIn('92 bpm', enhancement.prompt)
        self.assertIn('C major', enhancement.prompt)
        self.assertTrue(CreditReservation.objects.filter(
            reference_id=str(enhancement.id), reference_type='humming_enhancement',
            status='reserved').exists())
        delay.assert_called_once_with(str(enhancement.id))

        body = enhancement_service.build_modal_body(enhancement)
        self.assertEqual(body['ref_s3_key'], job.output_keys['cancion-2.mp3'])
        self.assertEqual(body['ref_audio_strength'], 0.8)
        self.assertEqual(body['bpm'], 92)
        self.assertEqual(body['keyscale'], 'C major')

    def test_enhance_without_version_picks_the_base_from_the_style(self):
        job = self._completed_job()  # versiones: 1 balada, 2 lofi
        payload = {'style': 'bolero'}
        with patch('apps.humming.tasks.submit_humming_enhancement.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(f'/api/humming/{job.id}/enhance/', payload, format='json')
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(HummingEnhancement.objects.get().version_number, 1)  # bolero → balada

        HummingEnhancement.objects.all().delete()
        with patch('apps.humming.tasks.submit_humming_enhancement.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(f'/api/humming/{job.id}/enhance/', {'style': 'jazz'}, format='json')
        self.assertEqual(HummingEnhancement.objects.get().version_number, 2)  # jazz → lo-fi

    def test_custom_style_requires_text(self):
        job = self._completed_job()

        response, _ = self._enhance(job, style='custom', custom_style='  ')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(HummingEnhancement.objects.exists())

    def test_cannot_enhance_unfinished_job(self):
        job = self._make_job()

        response, _ = self._enhance(job)

        self.assertEqual(response.status_code, 400)

    def test_without_credits_returns_402(self):
        job = self._completed_job()
        User.objects.filter(id=self.user.id).update(credit_balance=0)

        response, delay = self._enhance(job)

        self.assertEqual(response.status_code, 402)
        self.assertFalse(HummingEnhancement.objects.exists())
        delay.assert_not_called()

    @override_settings(MODAL_ENDPOINT_FROM_REFERENCE='')
    def test_unavailable_without_modal_endpoint(self):
        job = self._completed_job()

        response, _ = self._enhance(job)

        self.assertEqual(response.status_code, 503)

    @patch('apps.humming.tasks.poll_humming_enhancement.apply_async')
    @patch('ml.modal_client.submit_music_job', return_value={'remote_job_id': 'remote-1'})
    def test_submit_marks_processing_and_polls(self, submit, poll):
        job = self._completed_job()
        self._enhance(job)
        enhancement = HummingEnhancement.objects.get()

        tasks.submit_humming_enhancement.apply(args=[str(enhancement.id)])

        enhancement.refresh_from_db()
        self.assertEqual(enhancement.status, 'processing')
        self.assertEqual(enhancement.remote_job_id, 'remote-1')
        self.assertEqual(submit.call_args.args[0], 'https://modal.example/from-reference')
        poll.assert_called_once()

    def _assert_submit_fails_and_releases(self):
        enhancement = HummingEnhancement.objects.get()
        tasks.submit_humming_enhancement.apply(args=[str(enhancement.id)])
        enhancement.refresh_from_db()
        self.assertEqual(enhancement.status, 'failed')
        self.assertTrue(CreditReservation.objects.filter(
            reference_id=str(enhancement.id), status='released',
        ).exists())

    @patch('ml.modal_client.submit_music_job')
    def test_submit_without_endpoint_fails_instead_of_staying_queued(self, submit):
        job = self._completed_job()
        self._enhance(job)

        with override_settings(MODAL_ENDPOINT_FROM_REFERENCE=''):
            self._assert_submit_fails_and_releases()
        submit.assert_not_called()

    @patch('ml.modal_client.submit_music_job', side_effect=ValueError('no es JSON'))
    def test_submit_unexpected_error_fails_instead_of_staying_queued(self, _submit):
        job = self._completed_job()
        self._enhance(job)

        self._assert_submit_fails_and_releases()

    def _complete_with_variants(self, job):
        self._enhance(job)
        enhancement = HummingEnhancement.objects.get()
        HummingEnhancement.objects.filter(id=enhancement.id).update(
            status='processing', remote_job_id='remote-1', started_at=timezone.now()
        )
        resultado = {
            'status': 'completed', 'progress_pct': 100, 's3_key': 'v1.mp3',
            'variant_keys': ['v1.mp3', 'v2.mp3', 'v3.mp3'],
            'cover_image_s3_key': 'cover.png', 'categories': [],
        }
        with patch('ml.modal_client.get_music_job_status', return_value=resultado):
            tasks.poll_humming_enhancement.apply(args=[str(enhancement.id)])
            tasks.poll_humming_enhancement.apply(args=[str(enhancement.id)])
        enhancement.refresh_from_db()
        return enhancement

    def test_body_asks_modal_for_three_variants(self):
        job = self._completed_job()
        self._enhance(job)

        body = enhancement_service.build_modal_body(HummingEnhancement.objects.get())

        self.assertEqual(body['variants'], 3)

    def test_completed_poll_stores_variants_and_charges_once(self):
        job = self._completed_job()
        balance_before = User.objects.get(id=self.user.id).credit_balance

        enhancement = self._complete_with_variants(job)

        self.assertEqual(enhancement.status, 'completed')
        self.assertEqual(enhancement.variant_keys, ['v1.mp3', 'v2.mp3', 'v3.mp3'])
        self.assertIsNone(enhancement.song)  # la canción se crea al elegir
        self.assertEqual(User.objects.get(id=self.user.id).credit_balance, balance_before - 1)
        detail = self.client.get(f'/api/humming/{job.id}/').data['enhancements'][0]
        self.assertEqual([v['number'] for v in detail['variants']], [1, 2, 3])
        self.assertTrue(detail['variants'][1]['audio_url'].endswith('v2.mp3'))
        self.assertTrue(detail['cover_url'].endswith('cover.png'))

    def test_completed_enhancement_schedules_similarity_measurement(self):
        job = self._completed_job()
        with patch('apps.humming.tasks.measure_humming_similarity.delay') as measure:
            with self.captureOnCommitCallbacks(execute=True):
                enhancement = self._complete_with_variants(job)

        measure.assert_called_once_with(str(enhancement.id))

    @patch('ml.storage_client.generate_presigned_url', side_effect=lambda key, *a, **k: f'https://signed/{key}')
    @patch('requests.post')
    def test_similarity_is_measured_by_the_worker_and_exposed_per_variant(self, post, _signed):
        job = self._completed_job()
        enhancement = self._complete_with_variants(job)
        post.return_value = _response(200, {'resultados': [
            {'puntaje': 0.45, 'nivel': 'alto'}, {'puntaje': None, 'nivel': None},
            {'puntaje': 0.2, 'nivel': 'medio'},
        ]})

        tasks.measure_humming_similarity.apply(args=[str(enhancement.id)])

        url, = post.call_args.args
        self.assertEqual(url, 'http://tarareo:8000/parecido')
        body = post.call_args.kwargs['json']
        self.assertTrue(body['arregloUrl'].endswith(job.output_keys['arreglo.mid']))
        self.assertEqual([u.rsplit('/', 1)[-1] for u in body['audioUrls']], ['v1.mp3', 'v2.mp3', 'v3.mp3'])
        variants = self.client.get(f'/api/humming/{job.id}/').data['enhancements'][0]['variants']
        self.assertEqual([v['similarity'] for v in variants],
                         [{'puntaje': 0.45, 'nivel': 'alto'}, None, {'puntaje': 0.2, 'nivel': 'medio'}])

    @patch('ml.storage_client.generate_presigned_url', side_effect=lambda key, *a, **k: f'https://signed/{key}')
    @patch('requests.post')
    def test_similarity_failure_keeps_the_enhancement_usable(self, post, _signed):
        import requests

        job = self._completed_job()
        enhancement = self._complete_with_variants(job)
        post.side_effect = requests.ConnectionError('worker caído')

        with patch.object(tasks.measure_humming_similarity, 'retry', side_effect=RuntimeError('sin reintento')):
            with self.assertRaises(RuntimeError):
                tasks.measure_humming_similarity.apply(args=[str(enhancement.id)], throw=True)

        enhancement.refresh_from_db()
        self.assertEqual(enhancement.status, 'completed')
        self.assertEqual(enhancement.variant_similarity, [])

    @patch('ml.storage_client.delete_file')
    def test_choose_variant_creates_song_and_deletes_the_others(self, delete_file):
        job = self._completed_job()
        enhancement = self._complete_with_variants(job)
        url = f'/api/humming/enhancements/{enhancement.id}/choose/'

        with self.captureOnCommitCallbacks(execute=True):
            first = self.client.post(url, {'variant': 2}, format='json')
        again = self.client.post(url, {'variant': 2}, format='json')
        other = self.client.post(url, {'variant': 1}, format='json')

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(again.status_code, 201)
        self.assertEqual(other.status_code, 409)
        enhancement.refresh_from_db()
        song = enhancement.song
        self.assertEqual(enhancement.chosen_variant, 2)
        self.assertEqual(song.source_type, 'hummed')
        self.assertEqual(song.audio_s3_key, 'v2.mp3')
        self.assertEqual(song.thumbnail_s3_key, 'cover.png')
        self.assertIn('Cumbia', song.title)
        self.assertEqual(sorted(c.args[0] for c in delete_file.call_args_list), ['v1.mp3', 'v3.mp3'])
        detail = self.client.get(f'/api/humming/{job.id}/').data['enhancements'][0]
        self.assertEqual([v['number'] for v in detail['variants']], [2])

    def test_other_users_cannot_choose_a_variant(self):
        job = self._completed_job()
        enhancement = self._complete_with_variants(job)
        other = User.objects.create_user(email='ajeno@example.com', password='x', full_name='Ajeno')
        client = APIClient()
        client.force_authenticate(other)

        response = client.post(
            f'/api/humming/enhancements/{enhancement.id}/choose/', {'variant': 1}, format='json'
        )

        self.assertEqual(response.status_code, 404)

    @patch('ml.modal_client.get_music_job_status', return_value={
        'status': 'failed', 'progress_pct': 0, 'error_message': 'GPU caída',
    })
    def test_failed_poll_releases_credits(self, _status):
        job = self._completed_job()
        self._enhance(job)
        enhancement = HummingEnhancement.objects.get()
        HummingEnhancement.objects.filter(id=enhancement.id).update(
            status='processing', remote_job_id='remote-1', started_at=timezone.now()
        )

        tasks.poll_humming_enhancement.apply(args=[str(enhancement.id)])

        enhancement.refresh_from_db()
        self.assertEqual(enhancement.status, 'failed')
        self.assertEqual(enhancement.error_message, 'GPU caída')
        self.assertEqual(
            CreditReservation.objects.get(reference_id=str(enhancement.id)).status, 'released'
        )


@override_settings(
    MODAL_ENDPOINT_FROM_REFERENCE='https://modal.example/from-reference',
    HUMMING_AI_VERSIONS=True,
)
class HummingAutomaticAiTests(HummingTestBase):
    """El tarareo entrega directamente sus versiones producidas con IA (1 crédito en total)."""

    def _completed_job_with_ai(self):
        job = self._make_job()
        with patch('apps.humming.tasks.submit_humming_enhancement.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                services.apply_worker_result(str(job.id), _completed_payload(job.id, versions=(1, 2, 3)))
        job.refresh_from_db()
        return job, delay

    def _finish_ai(self, job, number, key, status='completed'):
        item = job.enhancements.get(automatic=True, version_number=number)
        HummingEnhancement.objects.filter(id=item.id).update(
            status=status, variant_keys=[key] if status == 'completed' else [],
            cover_s3_key=f'cover-{number}.png' if status == 'completed' else None,
        )

    def test_each_version_gets_an_automatic_ai_version_without_extra_credits(self):
        job, delay = self._completed_job_with_ai()

        automaticas = job.enhancements.filter(automatic=True).order_by('version_number')
        self.assertEqual([e.version_number for e in automaticas], [1, 2, 3])
        self.assertEqual([e.style_label for e in automaticas], ['Balada', 'Lo-fi', 'Lo-fi'])
        self.assertIn('92 bpm', automaticas[0].prompt)
        self.assertEqual(delay.call_count, 3)
        self.assertFalse(CreditReservation.objects.filter(reference_type='humming_enhancement').exists())
        body = enhancement_service.build_modal_body(automaticas[0])
        self.assertEqual(body['variants'], 1)

    def test_ai_versions_are_created_only_once(self):
        job, _ = self._completed_job_with_ai()

        with patch('apps.humming.tasks.submit_humming_enhancement.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                enhancement_service.start_automatic_versions(str(job.id))

        self.assertEqual(job.enhancements.filter(automatic=True).count(), 3)
        delay.assert_not_called()

    def test_detail_shows_ai_status_per_version_and_hides_them_from_the_panel(self):
        job, _ = self._completed_job_with_ai()
        self._finish_ai(job, 1, 'ai-1.mp3')

        data = self.client.get(f'/api/humming/{job.id}/').data

        ai = {v['number']: v['ai'] for v in data['versions']}
        self.assertEqual(ai[1]['status'], 'completed')
        self.assertTrue(ai[1]['audio_url'].endswith('ai-1.mp3'))
        self.assertTrue(ai[1]['cover_url'].endswith('cover-1.png'))
        self.assertEqual(ai[2]['status'], 'queued')
        self.assertIsNone(ai[2]['audio_url'])
        self.assertEqual(data['enhancements'], [])

    def test_cannot_choose_while_its_ai_version_is_in_progress(self):
        job, _ = self._completed_job_with_ai()

        response = self.client.post(f'/api/humming/{job.id}/choose/', {'version': 1}, format='json')

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Song.objects.exists())

    @patch('apps.humming.services._delete_keys')
    def test_choose_saves_the_ai_audio_and_deletes_the_other_ai_versions(self, delete_keys):
        job, _ = self._completed_job_with_ai()
        for numero in (1, 2, 3):
            self._finish_ai(job, numero, f'ai-{numero}.mp3')

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/humming/{job.id}/choose/', {'version': 2}, format='json')

        self.assertEqual(response.status_code, 201, response.data)
        song = Song.objects.get()
        self.assertEqual(song.audio_s3_key, 'ai-2.mp3')
        self.assertEqual(song.thumbnail_s3_key, 'cover-2.png')
        self.assertEqual(
            sorted(delete_keys.call_args.args[0]), ['ai-1.mp3', 'ai-3.mp3', 'cover-1.png', 'cover-3.png']
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.credit_balance, 4)  # solo el crédito del tarareo

    def test_failed_ai_falls_back_to_the_original_version(self):
        job, _ = self._completed_job_with_ai()
        self._finish_ai(job, 1, '', status='failed')

        response = self.client.post(f'/api/humming/{job.id}/choose/', {'version': 1}, format='json')

        self.assertEqual(response.status_code, 201, response.data)
        song = Song.objects.get()
        self.assertEqual(song.audio_s3_key, job.output_keys['cancion.mp3'])
        self.assertIsNone(song.thumbnail_s3_key)

    @override_settings(HUMMING_AI_VERSIONS=False)
    def test_can_be_disabled(self):
        job, delay = self._completed_job_with_ai()

        self.assertFalse(job.enhancements.exists())
        delay.assert_not_called()


class HummingWarmupTests(HummingTestBase):
    @patch('apps.humming.tasks.warm_ai_gpu.delay')
    @patch('apps.humming.tasks.dispatch_humming_job.delay')
    def test_upload_also_warms_up_the_ai_gpu(self, _dispatch, warm):
        archivo = SimpleUploadedFile('tarareo.webm', b'audio', content_type='audio/webm')

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/api/humming/', {'file': archivo}, format='multipart')

        warm.assert_called_once_with()

    @override_settings(
        MODAL_ENDPOINT_FROM_REFERENCE='https://modal.example/from-reference',
        MODAL_ENDPOINT_WARM_COVER='https://modal.example/warm-cover',
        HUMMING_AI_VERSIONS=True,
    )
    @patch('requests.post', return_value=_response(200))
    def test_warm_task_calls_modal_with_proxy_auth(self, post):
        tasks.warm_ai_gpu.apply()

        self.assertEqual(post.call_args.args[0], 'https://modal.example/warm-cover')
        self.assertIn('Modal-Key', post.call_args.kwargs['headers'])

    @override_settings(MODAL_ENDPOINT_WARM_COVER='https://modal.example/warm-cover')
    @patch('requests.post')
    def test_warm_task_does_nothing_when_ai_is_off(self, post):
        with override_settings(MODAL_ENDPOINT_FROM_REFERENCE=''):
            tasks.warm_ai_gpu.apply()

        post.assert_not_called()

    def test_humming_tasks_use_their_own_queue(self):
        from django.conf import settings as django_settings

        self.assertEqual(django_settings.CELERY_TASK_ROUTES['apps.humming.tasks.*'], {'queue': 'humming'})



class HummingStyleCatalogTests(TestCase):
    def test_catalog_has_the_new_styles_and_valid_bases(self):
        from apps.humming.styles import STYLES, WORKER_PRESETS

        keys = {s.key for s in STYLES}
        self.assertGreaterEqual(len(STYLES), 36)
        self.assertTrue({'merengue', 'bolero', 'saya', 'tinku', 'blues', 'metal'} <= keys)
        self.assertEqual(len(keys), len(STYLES))  # sin claves repetidas
        for style in STYLES:
            self.assertTrue(style.base, style.key)
            self.assertTrue(set(style.base) <= set(WORKER_PRESETS), style.key)

    def test_pick_base_version_prefers_the_closest_worker_style(self):
        from apps.humming.styles import pick_base_version

        versiones = [
            {'numero': 1, 'estilo': 'lofi'},
            {'numero': 2, 'estilo': 'balada'},
            {'numero': 3, 'estilo': 'epico'},
        ]
        self.assertEqual(pick_base_version('caporales', versiones), 3)  # bronces y marcha
        self.assertEqual(pick_base_version('bolero', versiones), 2)     # lento
        self.assertEqual(pick_base_version('jazz', versiones), 1)       # suave
        self.assertEqual(pick_base_version('custom', versiones), 1)     # texto libre: la principal
        self.assertEqual(pick_base_version('caporales', versiones[:2]), 1)  # sin épica: la principal
        self.assertIsNone(pick_base_version('pop', []))
