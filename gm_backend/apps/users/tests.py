from rest_framework.test import APITestCase

from apps.users.models import Role, UserDevice, UserRole
from apps.users.services import create_user

ME_URL = "/api/auth/me/"


class MeProfileUpdateTests(APITestCase):
    def setUp(self):
        self.user = create_user(email="perfil@test.com", password="clave12345", full_name="Nombre Viejo")
        self.user.credit_balance = 10
        self.user.save(update_fields=["credit_balance"])

    def test_patch_actualiza_nombre(self):
        self.client.force_authenticate(self.user)
        res = self.client.patch(ME_URL, {"full_name": "Nombre Nuevo"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["full_name"], "Nombre Nuevo")
        self.assertIn("credit_balance", res.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Nombre Nuevo")

    def test_patch_ignora_campos_protegidos(self):
        Role.objects.get_or_create(name="admin")
        self.client.force_authenticate(self.user)
        res = self.client.patch(
            ME_URL,
            {"credit_balance": 9999, "role": "admin", "email": "otro@test.com", "is_staff": True},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.credit_balance, 10)
        self.assertEqual(self.user.email, "perfil@test.com")
        self.assertFalse(self.user.is_staff)
        self.assertFalse(UserRole.objects.filter(user=self.user, role__name="admin").exists())
        self.assertEqual(res.data["role"], "user")

    def test_patch_sin_autenticacion_401(self):
        res = self.client.patch(ME_URL, {"full_name": "X"}, format="json")
        self.assertEqual(res.status_code, 401)


class FCMDeviceTests(APITestCase):
    def setUp(self):
        self.user = create_user(
            email='fcm@test.com',
            password='clave12345',
            full_name='Usuario FCM',
        )
        self.client.force_authenticate(self.user)

    def test_registra_token_con_plataforma_y_dispositivo(self):
        response = self.client.post(
            '/api/auth/fcm-token/',
            {
                'fcm_token': 'token-android',
                'platform': 'android',
                'device_id': 'device-1',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        device = UserDevice.objects.get(user=self.user, token='token-android')
        self.assertEqual(device.platform, 'android')
        self.assertEqual(device.device_id, 'device-1')
        self.assertTrue(device.is_active)

    def test_rechaza_token_invalido_o_plataforma_desconocida(self):
        empty = self.client.post(
            '/api/auth/fcm-token/',
            {'fcm_token': '   '},
            format='json',
        )
        invalid_platform = self.client.post(
            '/api/auth/fcm-token/',
            {'fcm_token': 'token', 'platform': 'desktop'},
            format='json',
        )

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(invalid_platform.status_code, 400)

    def test_nuevo_token_del_mismo_dispositivo_desactiva_el_anterior(self):
        UserDevice.objects.create(
            user=self.user,
            token='token-old',
            platform='android',
            device_id='device-1',
        )

        response = self.client.post(
            '/api/auth/fcm-token/',
            {
                'fcm_token': 'token-new',
                'platform': 'android',
                'device_id': 'device-1',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserDevice.objects.get(token='token-old').is_active)
        self.assertTrue(UserDevice.objects.get(token='token-new').is_active)

    def test_logout_desactiva_el_dispositivo_indicado(self):
        UserDevice.objects.create(
            user=self.user,
            token='token-logout',
            platform='android',
            device_id='device-logout',
        )

        response = self.client.post(
            '/api/auth/logout/',
            {'device_id': 'device-logout'},
            format='json',
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(UserDevice.objects.get(token='token-logout').is_active)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.fcm_token)
