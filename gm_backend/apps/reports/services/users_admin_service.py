"""Servicios de listado y actualización de usuarios y roles para administradores."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Prefetch, Q
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import log_action
from apps.reports.serializers import AdminUserUpdateSerializer


def _resolve_plan_name(user) -> str:
    subs = getattr(user, 'active_subscriptions_list', None) or []
    return subs[0].plan.name if subs else 'Free'


def _resolve_role_name(user) -> str:
    if user.is_staff:
        return 'admin'
    roles = getattr(user, 'prefetched_user_roles', None)
    if roles is None:
        roles = list(user.user_roles.select_related('role').all())
    for user_role in roles:
        if user_role.role.name == 'admin':
            return 'admin'
    return roles[0].role.name if roles else 'user'


def _serialize_admin_user(user) -> dict:
    return {
        'id': str(user.id),
        'full_name': user.full_name,
        'email': user.email,
        'credit_balance': user.credit_balance,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'role': _resolve_role_name(user),
        'plan_name': _resolve_plan_name(user),
        'created_at': user.created_at,
    }


def _sync_user_roles(target_user, make_admin: bool) -> None:
    """Sincroniza la tabla UserRole con el estado administrativo del usuario."""
    from apps.users.models import Role, UserRole
    from apps.users.services import assign_default_role

    if make_admin:
        admin_role, _ = Role.objects.get_or_create(name='admin', defaults={'is_system': True})
        UserRole.objects.filter(user=target_user).exclude(role=admin_role).delete()
        UserRole.objects.get_or_create(user=target_user, role=admin_role)
    else:
        UserRole.objects.filter(user=target_user, role__name='admin').delete()
        assign_default_role(target_user)


def list_admin_users(search: str = '') -> list[dict]:
    """Lista los últimos 200 usuarios no eliminados con su plan y rol."""
    from apps.credits.models import UserSubscription
    from apps.users.models import User, UserRole

    active_subs_prefetch = Prefetch(
        'subscriptions',
        queryset=UserSubscription.objects.filter(
            status='active', deleted_at__isnull=True
        ).select_related('plan').order_by('-created_at'),
        to_attr='active_subscriptions_list',
    )
    roles_prefetch = Prefetch(
        'user_roles',
        queryset=UserRole.objects.select_related('role'),
        to_attr='prefetched_user_roles',
    )

    users = User.objects.filter(deleted_at__isnull=True).prefetch_related(
        active_subs_prefetch, roles_prefetch
    ).order_by('-created_at')

    clean_search = (search or '').strip()
    if clean_search:
        users = users.filter(
            Q(full_name__icontains=clean_search) | Q(email__icontains=clean_search)
        )

    return [_serialize_admin_user(u) for u in users[:200]]


def update_admin_user(*, acting_user, user_id, payload: dict, request=None) -> dict:
    """Actualiza permisos/estado de un usuario con bloqueo de auto-degradación."""
    from apps.credits.models import UserSubscription
    from apps.users.models import User

    serializer = AdminUserUpdateSerializer(data=payload, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    target = User.objects.filter(id=user_id, deleted_at__isnull=True).first()
    if not target:
        raise NotFound('Usuario no encontrado.')

    desired_staff = data['is_staff'] if 'is_staff' in data else (
        data['role'] == 'admin' if 'role' in data else None
    )

    if str(target.pk) == str(acting_user.pk):
        if desired_staff is False:
            raise ValidationError('No puedes quitarte el rol de administrador a ti mismo.')
        if data.get('is_active') is False:
            raise ValidationError('No puedes desactivar tu propia cuenta.')

    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=target.pk)
        changes: dict[str, dict] = {}
        update_fields: list[str] = []

        if desired_staff is not None and locked.is_staff != desired_staff:
            changes['is_staff'] = {'before': locked.is_staff, 'after': desired_staff}
            locked.is_staff = desired_staff
            update_fields.append('is_staff')

        if 'is_active' in data and locked.is_active != data['is_active']:
            changes['is_active'] = {'before': locked.is_active, 'after': data['is_active']}
            locked.is_active = data['is_active']
            update_fields.append('is_active')

        if hasattr(locked, 'role') and desired_staff is not None:
            new_role_value = 'admin' if desired_staff else 'user'
            if getattr(locked, 'role') != new_role_value:
                changes['role'] = {'before': getattr(locked, 'role'), 'after': new_role_value}
                setattr(locked, 'role', new_role_value)
                update_fields.append('role')

        if update_fields:
            update_fields.append('updated_at')
            locked.save(update_fields=update_fields)

        if desired_staff is not None:
            _sync_user_roles(locked, make_admin=desired_staff)

        log_action(
            acting_user,
            action='admin.user.update',
            resource_type='user',
            resource_id=str(locked.id),
            details={
                'changes': changes,
                'requested': dict(data),
            },
            request=request,
        )

    active_subs_prefetch = Prefetch(
        'subscriptions',
        queryset=UserSubscription.objects.filter(
            status='active', deleted_at__isnull=True
        ).select_related('plan').order_by('-created_at'),
        to_attr='active_subscriptions_list',
    )
    refreshed = User.objects.prefetch_related(active_subs_prefetch, 'user_roles__role').get(
        pk=target.pk
    )
    return _serialize_admin_user(refreshed)
