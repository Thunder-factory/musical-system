from unittest import skipUnless
from uuid import uuid4
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from firebase_admin import db

from apps.notifications.firebase import get_firebase_app, send_push
from apps.notifications.models import Notification
from apps.notifications.services import notify_user
from apps.users.models import User


class SendPushTest(SimpleTestCase):
    @override_settings(PUSH_NOTIFICATIONS_ENABLED=True)
    @patch('apps.notifications.firebase.messaging.send', return_value='projects/test/messages/1')
    @patch('apps.notifications.firebase.get_firebase_app')
    def test_configures_android_high_priority_and_channel(self, mock_get_app, mock_send):
        fake_app = MagicMock()
        mock_get_app.return_value = fake_app

        result = send_push(
            token='android-fcm-token',
            title='Tu karaoke está listo',
            body='Ya puedes cantar con letra sincronizada.',
            data={'type': 'karaoke_ready', 'reference_id': 'track-1'},
        )

        self.assertEqual(result, 'projects/test/messages/1')
        mock_send.assert_called_once()
        sent_message = mock_send.call_args.args[0]
        self.assertEqual(mock_send.call_args.kwargs['app'], fake_app)
        self.assertEqual(sent_message.token, 'android-fcm-token')
        self.assertEqual(sent_message.notification.title, 'Tu karaoke está listo')
        self.assertEqual(sent_message.notification.body, 'Ya puedes cantar con letra sincronizada.')
        self.assertIsNotNone(sent_message.android)
        self.assertEqual(sent_message.android.priority, 'high')
        self.assertIsNotNone(sent_message.android.notification)
        self.assertEqual(sent_message.android.notification.channel_id, 'musicai_default')
        self.assertEqual(sent_message.android.notification.sound, 'default')


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
            data={'reference_id': 'export-123', 'type': 'mix_ready'},
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
    def test_notify_user_supports_karaoke_translation_and_humming_types(self, send_push):
        cases = [
            (
                'karaoke_ready',
                'karaoke-1',
                'Tu karaoke está listo',
                'Ya puedes cantar con letra sincronizada.',
            ),
            (
                'translation_ready',
                'translation-1',
                'Tu traducción está lista',
                'Ya puedes ver tu video doblado.',
            ),
            (
                'humming_ready',
                'humming-1',
                'Tu tarareo está listo',
                'Ya puedes escuchar las versiones generadas.',
            ),
        ]

        for notif_type, ref_id, expected_title, expected_message in cases:
            with self.subTest(type=notif_type):
                send_push.reset_mock()
                notify_user(self.user, type=notif_type, reference_id=ref_id)

                notification = Notification.objects.get(
                    user=self.user,
                    type=notif_type,
                    reference_id=ref_id,
                )
                self.assertEqual(notification.title, expected_title)
                self.assertEqual(notification.message, expected_message)
                send_push.assert_called_once_with(
                    token='test-fcm-token',
                    title=expected_title,
                    body=expected_message,
                    data={'reference_id': ref_id, 'type': notif_type},
                )


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
