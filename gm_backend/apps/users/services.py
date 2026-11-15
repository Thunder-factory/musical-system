from __future__ import annotations
from django.db import transaction

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.users.models import User

@transaction.atomic
def create_user(email: str, password: str, full_name: str) -> User:
    """
    Crea un nuevo usuario con rol por defecto asignado.

    Args:
        email: Dirección de correo electrónico única del usuario.
        password: Contraseña en texto plano (se hashea internamente).
        full_name: Nombre completo del usuario.

    Returns:
        Instancia del usuario recién creado con creditos asignados.
    """
    from apps.users.models import User
    from apps.credits.services.free_plan_service import assign_free_plan

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
    )

    assign_default_role(user)
    assign_free_plan(user)

    return user


def assign_default_role(user: User) -> None:
    """
    Asigna el rol por defecto ('user') a un usuario recién creado.

    Si el rol no existe en la base de datos se crea automáticamente
    como rol de sistema.

    Args:
        user: Instancia del usuario al que se asignará el rol.
    """
    from apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(name="user", defaults={"is_system": True})
    UserRole.objects.get_or_create(user=user, role=role)
