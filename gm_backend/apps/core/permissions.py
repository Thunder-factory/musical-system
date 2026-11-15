from rest_framework.permissions import BasePermission


def _is_admin(user):
    return user.is_authenticated and (
        user.is_staff
        or user.user_roles.filter(role__name="admin").exists()
    )


class IsAdmin(BasePermission):
    """El usuario tiene rol 'admin' o es staff de Django."""
    def has_permission(self, request, view):
        return _is_admin(request.user)


class IsOwnerOrAdmin(BasePermission):
    """El objeto pertenece al usuario autenticado, o es admin."""
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if _is_admin(request.user):
            return True
        return obj.user_id == request.user.id
