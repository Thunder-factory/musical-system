from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

if TYPE_CHECKING:
    from apps.users.models import User


class InsufficientCreditsError(Exception):
    """El usuario no tiene créditos suficientes para la operación."""


def check_balance(user: User, required: int = 1) -> bool:
    """
    Verifica si el usuario tiene suficientes créditos para una operación.

    Args:
        user: Usuario cuyo balance se desea comprobar.
        required: Cantidad mínima de créditos necesarios. Por defecto 1.

    Returns:
        True si el balance del usuario es mayor o igual al requerido,
        False en caso contrario.
    """
    from apps.credits.models import CreditReservation

    reserved = CreditReservation.objects.filter(
        user_id=user.pk,
        status='reserved',
    ).filter(_active_reservation_query()).aggregate(total=Sum('amount'))['total'] or 0
    return user.credit_balance - reserved >= required


def _active_reservation_query():
    return Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())


def reserve_credits(
    user: User,
    amount: int,
    reference_id: str,
    reference_type: str,
    expires_in_seconds: int = 3600,
):
    """Reserve credits idempotently for an asynchronous operation."""
    from apps.credits.models import CreditReservation
    from apps.users.models import User

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        reservation = CreditReservation.objects.select_for_update().filter(
            user=locked_user,
            reference_id=reference_id,
            reference_type=reference_type,
        ).first()
        now = timezone.now()
        if reservation and reservation.status == 'confirmed':
            return reservation
        if reservation and reservation.status == 'reserved' and (
            reservation.expires_at is None or reservation.expires_at > now
        ):
            return reservation

        reserved = CreditReservation.objects.filter(
            user=locked_user,
            status='reserved',
        ).filter(_active_reservation_query()).aggregate(total=Sum('amount'))['total'] or 0
        if locked_user.credit_balance - reserved < amount:
            raise InsufficientCreditsError("Sin créditos suficientes.")

        values = {
            'amount': amount,
            'status': 'reserved',
            'expires_at': now + timedelta(seconds=expires_in_seconds),
        }
        if reservation:
            for key, value in values.items():
                setattr(reservation, key, value)
            reservation.save(update_fields=[*values, 'updated_at'])
            return reservation
        return CreditReservation.objects.create(
            user=locked_user,
            reference_id=reference_id,
            reference_type=reference_type,
            **values,
        )


def confirm_reservation(reservation_id: str) -> None:
    from apps.credits.models import CreditReservation, CreditTransaction
    from apps.users.models import User

    expired = False
    with transaction.atomic():
        reservation_snapshot = CreditReservation.objects.get(id=reservation_id)
        user = User.objects.select_for_update().get(pk=reservation_snapshot.user_id)
        reservation = CreditReservation.objects.select_for_update().get(id=reservation_id)
        if reservation.status == 'confirmed':
            return
        if reservation.status != 'reserved':
            raise ValueError('La reserva de créditos ya fue liberada.')
        if reservation.expires_at and reservation.expires_at <= timezone.now():
            reservation.status = 'released'
            reservation.save(update_fields=['status', 'updated_at'])
            expired = True
        elif user.credit_balance < reservation.amount:
            raise InsufficientCreditsError("Sin créditos suficientes para confirmar la reserva.")
        else:
            user.credit_balance -= reservation.amount
            user.save(update_fields=['credit_balance'])
            CreditTransaction.objects.create(
                user=user,
                amount=-reservation.amount,
                balance_after=user.credit_balance,
                type=reservation.reference_type,
                reference_id=reservation.reference_id,
            )
            reservation.status = 'confirmed'
            reservation.save(update_fields=['status', 'updated_at'])
    if expired:
        raise ValueError('La reserva de créditos expiró.')


def release_reservation(reservation_id: str) -> None:
    from apps.credits.models import CreditReservation
    from apps.users.models import User

    with transaction.atomic():
        snapshot = CreditReservation.objects.get(id=reservation_id)
        User.objects.select_for_update().get(pk=snapshot.user_id)
        CreditReservation.objects.select_for_update().filter(
            id=reservation_id,
            status='reserved',
        ).update(status='released', updated_at=timezone.now())


def deduct_credits(
    user: User,
    amount: int,
    reference_id: str | None = None,
    reference_type: str | None = None,
) -> None:
    """
    Descuenta créditos del balance del usuario y registra la transacción.

    La operación es atómica: si falla el registro de la transacción se
    revierte también el cambio en el balance del usuario.

    Args:
        user: Usuario al que se le descontarán los créditos.
        amount: Cantidad de créditos a descontar (valor positivo).
        reference_id: Identificador del recurso que originó el descuento
            (p. ej. el ID de un job o canción). Opcional.
        reference_type: Tipo de operación que originó el descuento
            (p. ej. 'generation', 'stem'). Si no se proporciona se usa
            'generation'.
    """
    from apps.credits.models import CreditReservation, CreditTransaction
    from apps.users.models import User

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        reserved = CreditReservation.objects.filter(
            user=locked_user,
            status='reserved',
        ).filter(_active_reservation_query()).aggregate(total=Sum('amount'))['total'] or 0
        if locked_user.credit_balance - reserved < amount:
            raise InsufficientCreditsError("Sin créditos suficientes.")

        locked_user.credit_balance -= amount
        locked_user.save(update_fields=["credit_balance"])
        user.credit_balance = locked_user.credit_balance
        CreditTransaction.objects.create(
            user=locked_user,
            amount=-amount,
            balance_after=locked_user.credit_balance,
            type=reference_type or "generation",
            reference_id=reference_id,
        )


def grant_credits(
    user: User,
    amount: int,
    type: str = "monthly_grant",
    description: str | None = None,
) -> None:
    """
    Agrega créditos al balance del usuario y registra la transacción.

    Se invoca principalmente desde el webhook de Stripe cuando se confirma
    un pago o al ejecutar el grant mensual programado.

    Args:
        user: Usuario al que se le acreditarán los créditos.
        amount: Cantidad de créditos a agregar (valor positivo).
        type: Tipo de transacción. Por defecto 'monthly_grant'.
        description: Descripción opcional de la razón del otorgamiento.
    """
    from apps.credits.models import CreditTransaction
    from apps.users.models import User

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        locked_user.credit_balance += amount
        locked_user.save(update_fields=["credit_balance"])
        user.credit_balance = locked_user.credit_balance
        CreditTransaction.objects.create(
            user=locked_user,
            amount=amount,
            balance_after=user.credit_balance,
            type=type,
            description=description,
        )
