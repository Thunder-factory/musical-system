"""Servicios de métricas reales para el dashboard administrativo."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Prefetch, Sum
from django.db.models.functions import ExtractMonth
from django.utils import timezone

MONTH_LABELS = (
    'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
)
PAID_PAYMENT_STATUSES = ('succeeded', 'paid')
CANCELED_SUBSCRIPTION_STATUSES = ('canceled', 'cancelled')


def _resolve_plan_name(user) -> str:
    """Devuelve el nombre del plan activo prefetched o 'Free' por defecto."""
    subs = getattr(user, 'active_subscriptions_list', None) or []
    return subs[0].plan.name if subs else 'Free'


def _build_monthly_series(year: int) -> list[dict]:
    """Construye la serie mensual del año actual con ingresos, usuarios y canciones."""
    from apps.credits.models import Payment
    from apps.songs.models import Song
    from apps.users.models import User

    revenue_rows = (
        Payment.objects.filter(status__in=PAID_PAYMENT_STATUSES, created_at__year=year)
        .annotate(month=ExtractMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'))
    )
    revenue_by_month = {row['month']: float(row['total'] or 0.0) for row in revenue_rows}

    users_rows = (
        User.objects.filter(deleted_at__isnull=True, created_at__year=year)
        .annotate(month=ExtractMonth('created_at'))
        .values('month')
        .annotate(total=Count('id'))
    )
    users_by_month = {row['month']: int(row['total'] or 0) for row in users_rows}

    songs_rows = (
        Song.objects.filter(status='ready', deleted_at__isnull=True, created_at__year=year)
        .annotate(month=ExtractMonth('created_at'))
        .values('month')
        .annotate(total=Count('id'))
    )
    songs_by_month = {row['month']: int(row['total'] or 0) for row in songs_rows}

    return [
        {
            'month': month,
            'label': MONTH_LABELS[month - 1],
            'revenue_usd': round(revenue_by_month.get(month, 0.0), 2),
            'new_users': users_by_month.get(month, 0),
            'songs_generated': songs_by_month.get(month, 0),
        }
        for month in range(1, 13)
    ]


def _build_plans_distribution(total_users: int) -> list[dict]:
    """Calcula la distribución real de usuarios por plan activo y usuarios sin suscripción."""
    from apps.credits.models import CreditPlan, UserSubscription
    from apps.users.models import User

    active_plans = list(CreditPlan.objects.filter(is_active=True).order_by('price_usd', 'id'))
    sub_counts_rows = (
        UserSubscription.objects.filter(
            status='active',
            deleted_at__isnull=True,
            user__deleted_at__isnull=True,
            plan__is_active=True,
        )
        .values('plan_id')
        .annotate(users_count=Count('user_id', distinct=True))
    )
    sub_counts = {row['plan_id']: int(row['users_count']) for row in sub_counts_rows}

    users_without_active_sub = (
        User.objects.filter(deleted_at__isnull=True)
        .exclude(
            subscriptions__status='active',
            subscriptions__deleted_at__isnull=True,
            subscriptions__plan__is_active=True,
        )
        .count()
    )

    has_free_plan = any(plan.slug == 'free' for plan in active_plans)
    distribution: list[dict] = []

    for plan in active_plans:
        count = sub_counts.get(plan.id, 0)
        if plan.slug == 'free':
            count += users_without_active_sub
        pct = round((count / total_users) * 100, 1) if total_users > 0 else 0.0
        distribution.append({
            'slug': plan.slug,
            'name': plan.name,
            'users_count': count,
            'percentage': pct,
        })

    if not has_free_plan:
        pct = round((users_without_active_sub / total_users) * 100, 1) if total_users > 0 else 0.0
        distribution.insert(0, {
            'slug': 'free',
            'name': 'Free',
            'users_count': users_without_active_sub,
            'percentage': pct,
        })

    return distribution


def get_admin_dashboard_metrics() -> dict:
    """Agrega métricas reales desde PostgreSQL para el panel de administración."""
    from apps.credits.models import Payment, UserSubscription
    from apps.songs.models import GenerationJob, Song
    from apps.users.models import User

    now = timezone.now()
    last_30 = now - timedelta(days=30)

    total_users = User.objects.filter(deleted_at__isnull=True).count()
    new_users_30d = User.objects.filter(deleted_at__isnull=True, created_at__gte=last_30).count()
    active_subscriptions = UserSubscription.objects.filter(
        status='active',
        deleted_at__isnull=True,
        user__deleted_at__isnull=True,
    ).count()
    canceled_30d = UserSubscription.objects.filter(
        status__in=CANCELED_SUBSCRIPTION_STATUSES,
        updated_at__gte=last_30,
        deleted_at__isnull=True,
    ).count()

    churn_denominator = active_subscriptions + canceled_30d
    churn_rate_pct = (
        round((canceled_30d / churn_denominator) * 100, 2) if churn_denominator > 0 else 0.0
    )

    total_songs_generated = Song.objects.filter(status='ready', deleted_at__isnull=True).count()
    songs_last_30d = Song.objects.filter(
        status='ready', deleted_at__isnull=True, created_at__gte=last_30
    ).count()
    failed_jobs_30d = GenerationJob.objects.filter(
        status='failed', created_at__gte=last_30
    ).count()

    monthly_revenue = (
        Payment.objects.filter(
            status__in=PAID_PAYMENT_STATUSES,
            created_at__year=now.year,
            created_at__month=now.month,
        ).aggregate(total=Sum('amount'))['total']
    )
    annual_revenue = (
        Payment.objects.filter(
            status__in=PAID_PAYMENT_STATUSES,
            created_at__year=now.year,
        ).aggregate(total=Sum('amount'))['total']
    )

    active_subs_prefetch = Prefetch(
        'subscriptions',
        queryset=UserSubscription.objects.filter(
            status='active', deleted_at__isnull=True
        ).select_related('plan').order_by('-created_at'),
        to_attr='active_subscriptions_list',
    )
    recent_users_qs = (
        User.objects.filter(deleted_at__isnull=True)
        .prefetch_related(active_subs_prefetch)
        .order_by('-created_at')[:10]
    )
    recent_users = [
        {
            'id': str(u.id),
            'full_name': u.full_name,
            'email': u.email,
            'plan_name': _resolve_plan_name(u),
            'is_active': u.is_active,
            'is_staff': u.is_staff,
            'created_at': u.created_at,
        }
        for u in recent_users_qs
    ]

    return {
        'total_users': total_users,
        'new_users_30d': new_users_30d,
        'active_subscriptions': active_subscriptions,
        'total_songs_generated': total_songs_generated,
        'songs_last_30d': songs_last_30d,
        'failed_jobs_30d': failed_jobs_30d,
        'monthly_revenue_usd': round(float(monthly_revenue or 0.0), 2),
        'annual_revenue_usd': round(float(annual_revenue or 0.0), 2),
        'churn_rate_pct': churn_rate_pct,
        'monthly_series': _build_monthly_series(now.year),
        'plans_distribution': _build_plans_distribution(total_users),
        'recent_users': recent_users,
    }
