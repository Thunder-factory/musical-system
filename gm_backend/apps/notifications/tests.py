from unittest import skipUnless
from uuid import uuid4
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from firebase_admin import db

from apps.notifications.firebase import get_firebase_app
from apps.notifications.models import Notification
from apps.notifications.services import notify_user
from apps.users.models import User


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
