from rest_framework.test import APITestCase

from apps.users.models import Role, UserRole
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
