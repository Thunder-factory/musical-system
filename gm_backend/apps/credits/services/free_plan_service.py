
from django.db import transaction

from apps.credits.models import CreditPlan, UserSubscription
from apps.credits.services.credit_service import grant_credits


FREE_PLAN_DEFAULTS = {
    "name": "Free",
    "credits_per_month": 5,
    "price_usd": 0,
    "features": ["5 canciones/mes", "Calidad estandar"],
    "is_active": True,
}


@transaction.atomic
def assign_free_plan(user):
    """
    Asigna el plan Free y sus créditos iniciales.

    No modifica usuarios que ya tienen una suscripción.
    No duplica créditos si se ejecuta nuevamente.
    """
    if UserSubscription.objects.filter(user=user).exists():
        return False

    plan, _ = CreditPlan.objects.get_or_create(
        slug="free",
        defaults=FREE_PLAN_DEFAULTS,
    )

    if not plan.is_active:
        raise ValueError("El plan Free está inactivo")

    UserSubscription.objects.create(
        user=user,
        plan=plan,
        status="active",
    )

    grant_credits(
        user=user,
        amount=plan.credits_per_month,
        type="initial_grant",
        description="Créditos iniciales del plan Free",
    )

    return True
