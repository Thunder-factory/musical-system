"""Contexto dinámico del usuario (segundo bloque de sistema, no se cachea)."""


def _active_plan_name(user) -> str:
    subscription = (
        user.subscriptions.filter(status='active').select_related('plan').first()
    )
    return subscription.plan.name if subscription else 'sin plan activo'


def build_user_context(user, page: str = '') -> str:
    """Devuelve el bloque de contexto: nombre, saldo, plan y página actual."""
    name = (user.full_name or '').strip() or 'sin nombre'
    lines = [
        'Contexto del usuario actual (datos reales, úsalos para personalizar):',
        f'- Nombre: {name}',
        f'- Saldo de créditos: {user.credit_balance}',
        f'- Plan: {_active_plan_name(user)}',
        f'- Página actual: {page or "desconocida"}',
    ]
    return '\n'.join(lines)
