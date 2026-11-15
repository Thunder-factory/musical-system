from types import SimpleNamespace

from django.test import RequestFactory, TestCase

from apps.core.permissions import IsAdmin, IsOwnerOrAdmin
from apps.users.models import Role, User, UserRole


class AdminPermissionsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_role = Role.objects.create(name="admin", is_system=True)
        self.admin = User.objects.create_user(
            email="admin-role@example.com",
            password="test-password",
            full_name="Admin por rol",
        )
        UserRole.objects.create(user=self.admin, role=self.admin_role)
        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="test-password",
            full_name="Admin staff",
            is_staff=True,
        )
        self.user = User.objects.create_user(
            email="user@example.com",
            password="test-password",
            full_name="Usuario normal",
        )

    def test_is_admin_accepts_role_and_staff_users_only(self):
        permission = IsAdmin()

        self.assertTrue(permission.has_permission(self._request(self.admin), None))
        self.assertTrue(permission.has_permission(self._request(self.staff), None))
        self.assertFalse(permission.has_permission(self._request(self.user), None))

    def test_owner_or_admin_accepts_admin_role(self):
        permission = IsOwnerOrAdmin()
        own_object = SimpleNamespace(user_id=self.user.id)
        other_object = SimpleNamespace(user_id=self.admin.id)

        self.assertTrue(
            permission.has_object_permission(
                self._request(self.user), None, own_object
            )
        )
        self.assertTrue(
            permission.has_object_permission(
                self._request(self.admin), None, other_object
            )
        )
        self.assertFalse(
            permission.has_object_permission(
                self._request(self.user), None, other_object
            )
        )

    def _request(self, user):
        request = self.factory.get("/")
        request.user = user
        return request
