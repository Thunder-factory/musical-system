from unittest import skipUnless
from uuid import uuid4
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from firebase_admin import db
from rest_framework.test import APIClient

from apps.notifications.firebase import get_firebase_app
from apps.notifications.models import Notification
from apps.notifications.services import notify_user
from apps.users.models import User


@override_settings(PUSH_NOTIFICATIONS_ENABLED=True)
class NotifyUserTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='notifications-test@example.com',
            password='test-password',
            full_name='Notifications Test',
            fcm_token='test-fcm-token',
        )

    @patch('apps.notifications.services.send_push')
    def test_creates_notification_and_sends_push(self, send_push):
        notify_user(
            self.user,
            type='mix_ready',
            reference_id='export-123',
            title='Mix listo',
            message='Tu mix está listo.',
        )

        notification = Notification.objects.get(user=self.user)
        self.assertEqual(notification.type, 'mix_ready')
        self.assertEqual(notification.reference_id, 'export-123')
        self.assertEqual(notification.title, 'Mix listo')
        self.assertEqual(notification.message, 'Tu mix está listo.')
        send_push.assert_called_once_with(
            token='test-fcm-token',
            title='Mix listo',
            body='Tu mix está listo.',
            data={
                'reference_id': 'export-123',
                'type': 'mix_ready',
                'title': 'Mix listo',
                'body': 'Tu mix está listo.',
            },
        )

    @patch('apps.notifications.services.send_push', side_effect=RuntimeError('FCM down'))
    def test_push_failure_does_not_fail_internal_notification(self, send_push):
        notify_user(self.user, type='stem_ready', reference_id='stem-123')

        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                type='stem_ready',
                reference_id='stem-123',
            ).exists()
        )
        send_push.assert_called_once()

    @patch('apps.notifications.services.send_push')
    def test_push_message_can_hide_internal_error_details(self, send_push):
        notify_user(
            self.user,
            type='karaoke_failed',
            reference_id='karaoke-123',
            title='No se pudo generar el Karaoke',
            message='Detalle interno: Modal devolvió HTTP 502 con identificador remoto.',
            push_message='El procesamiento del Karaoke no pudo completarse.',
        )

        notification = Notification.objects.get(
            user=self.user,
            reference_id='karaoke-123',
        )
        self.assertIn('HTTP 502', notification.message)
        send_push.assert_called_once_with(
            token='test-fcm-token',
            title='No se pudo generar el Karaoke',
            body='El procesamiento del Karaoke no pudo completarse.',
            data={
                'reference_id': 'karaoke-123',
                'type': 'karaoke_failed',
                'title': 'No se pudo generar el Karaoke',
                'body': 'El procesamiento del Karaoke no pudo completarse.',
            },
        )

    @patch('apps.notifications.services.send_push')
    def test_same_event_is_created_and_pushed_only_once(self, send_push):
        notify_user(
            self.user,
            type='karaoke_ready',
            reference_id='karaoke-123',
        )
        notify_user(
            self.user,
            type='karaoke_ready',
            reference_id='karaoke-123',
        )

        notifications = Notification.objects.filter(
            user=self.user,
            event_key='karaoke_ready:karaoke-123',
        )
        self.assertEqual(notifications.count(), 1)
        send_push.assert_called_once()

    @patch('apps.notifications.services.send_push')
    def test_same_event_can_be_delivered_to_another_user(self, send_push):
        other = User.objects.create_user(
            email='notifications-other@example.com',
            password='test-password',
            full_name='Otro usuario',
            fcm_token='other-fcm-token',
        )

        notify_user(self.user, type='karaoke_ready', reference_id='karaoke-123')
        notify_user(other, type='karaoke_ready', reference_id='karaoke-123')

        self.assertEqual(
            Notification.objects.filter(event_key='karaoke_ready:karaoke-123').count(),
            2,
        )
        self.assertEqual(send_push.call_count, 2)

    @patch('apps.notifications.services.send_push', side_effect=[RuntimeError('FCM down'), None])
    def test_failed_push_can_be_retried_without_creating_duplicate(self, send_push):
        notify_user(self.user, type='karaoke_ready', reference_id='karaoke-retry')
        notify_user(self.user, type='karaoke_ready', reference_id='karaoke-retry')

        notification = Notification.objects.get(
            user=self.user,
            event_key='karaoke_ready:karaoke-retry',
        )
        self.assertEqual(Notification.objects.filter(
            user=self.user,
            event_key='karaoke_ready:karaoke-retry',
        ).count(), 1)
        self.assertEqual(notification.push_attempts, 2)
        self.assertIsNotNone(notification.push_sent_at)
        self.assertEqual(send_push.call_count, 2)

    @override_settings(PUSH_NOTIFICATIONS_ENABLED=False)
    @patch('apps.notifications.services.send_push')
    def test_disabled_push_does_not_call_firebase(self, send_push):
        notify_user(self.user, type='mix_ready', reference_id='mix-123')

        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                event_key='mix_ready:mix-123',
            ).exists()
        )
        send_push.assert_not_called()

    @patch('apps.notifications.services.send_push')
    def test_without_fcm_token_does_not_call_firebase(self, send_push):
        self.user.fcm_token = None
        self.user.save(update_fields=['fcm_token'])

        notify_user(self.user, type='song_ready', reference_id='song-123')

        send_push.assert_not_called()


class NotificationViewsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='notification-owner@example.com',
            password='test-password',
            full_name='Owner',
        )
        self.other = User.objects.create_user(
            email='notification-other@example.com',
            password='test-password',
            full_name='Other',
        )

    def test_user_only_sees_own_notifications(self):
        Notification.objects.create(
            user=self.user,
            type='song_ready',
            title='Propia',
            reference_id='song-1',
        )
        Notification.objects.create(
            user=self.other,
            type='song_ready',
            title='Ajena',
            reference_id='song-2',
        )
        self.client.force_authenticate(self.user)

        response = self.client.get('/api/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Propia')

    def test_marca_una_notificacion_como_leida(self):
        notification = Notification.objects.create(
            user=self.user,
            type='song_ready',
            title='Propia',
        )
        self.client.force_authenticate(self.user)

        response = self.client.patch(f'/api/notifications/{notification.id}/read/')

        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_no_puede_marcar_notificacion_ajena(self):
        notification = Notification.objects.create(
            user=self.other,
            type='song_ready',
            title='Ajena',
        )
        self.client.force_authenticate(self.user)

        response = self.client.patch(f'/api/notifications/{notification.id}/read/')

        self.assertEqual(response.status_code, 404)

    def test_marca_todas_como_leidas(self):
        Notification.objects.bulk_create([
            Notification(user=self.user, type='song_ready', title='Uno'),
            Notification(user=self.user, type='mix_ready', title='Dos'),
            Notification(user=self.other, type='song_ready', title='Ajena'),
        ])
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/notifications/read-all/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Notification.objects.filter(user=self.user, is_read=False).exists()
        )
        self.assertTrue(
            Notification.objects.filter(user=self.other, is_read=False).exists()
        )

    def test_all_supported_notification_types_are_declared(self):
        expected = {
            'song_ready', 'song_failed',
            'karaoke_ready', 'karaoke_failed',
            'stem_ready', 'stem_failed',
            'humming_ready', 'humming_failed',
            'translation_ready', 'translation_failed',
            'mix_ready', 'mix_failed',
            'faceswap_ready', 'faceswap_failed',
            'credit_grant', 'credit_low', 'system',
        }

        declared = {type_name for type_name, _ in Notification.TYPE_CHOICES}

        self.assertEqual(declared, expected)


@skipUnless(
    settings.FIREBASE_REALTIME_DATABASE_TEST_ENABLED,
    "Firebase Realtime Database integration test disabled",
)
class FirebaseRealtimeDatabaseTest(SimpleTestCase):
    """Verifica escritura, lectura y limpieza en Firebase Realtime Database."""

    def test_write_read_and_delete_temporary_value(self):
        app = get_firebase_app()
        reference = db.reference(f"/_integration_tests/{uuid4()}", app=app)
        expected = {"status": "ok", "source": "django-test"}

        try:
            reference.set(expected)
            self.assertEqual(reference.get(), expected)
        finally:
            reference.delete()
