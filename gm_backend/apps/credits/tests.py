from django.test import TestCase

from apps.credits.models import CreditPlan, CreditReservation, CreditTransaction, UserSubscription
from apps.credits.services.credit_service import (
    InsufficientCreditsError,
    confirm_reservation,
    deduct_credits,
    reserve_credits,
)
from apps.credits.services.free_plan_service import assign_free_plan
from apps.users.models import User
from apps.users.services import create_user


class FreePlanServiceTests(TestCase):
    def test_deduct_credits_cannot_make_balance_negative(self):
        user = User.objects.create_user(
            email="sin-creditos@example.com",
            password="test-password",
            full_name="Sin Créditos",
        )

        with self.assertRaises(InsufficientCreditsError):
            deduct_credits(user, amount=1, reference_type="generation")

        user.refresh_from_db()
        self.assertEqual(user.credit_balance, 0)
        self.assertFalse(CreditTransaction.objects.filter(user=user).exists())

    def test_new_user_gets_demo_credits_when_plan_is_missing(self):
        user = create_user(
            email="nuevo@example.com",
            password="test-password",
            full_name="Usuario Nuevo",
        )

        user.refresh_from_db()

        self.assertEqual(user.credit_balance, 5)
        self.assertTrue(
            UserSubscription.objects.filter(
                user=user,
                plan__slug="free",
                status="active",
            ).exists()
        )
        self.assertTrue(
            CreditTransaction.objects.filter(
                user=user,
                type="initial_grant",
                amount=5,
            ).exists()
        )

    def test_assign_free_plan_is_idempotent(self):
        plan = CreditPlan.objects.create(
            slug="free",
            name="Free",
            credits_per_month=5,
            price_usd=0,
            features=[],
        )
        user = User.objects.create_user(
            email="existente@example.com",
            password="test-password",
            full_name="Usuario Existente",
        )

        self.assertTrue(assign_free_plan(user))
        self.assertFalse(assign_free_plan(user))

        user.refresh_from_db()
        self.assertEqual(user.credit_balance, plan.credits_per_month)
        self.assertEqual(UserSubscription.objects.filter(user=user).count(), 1)
        self.assertEqual(CreditTransaction.objects.filter(user=user).count(), 1)

    def test_reservation_is_idempotent_and_confirmed_once(self):
        user = User.objects.create_user(
            email='reservation@example.com',
            password='test-password',
            full_name='Reserva',
        )
        user.credit_balance = 2
        user.save(update_fields=['credit_balance'])

        first = reserve_credits(user, 2, str(user.id), 'stem_job')
        second = reserve_credits(user, 2, str(user.id), 'stem_job')
        self.assertEqual(first.id, second.id)
        self.assertFalse(deduct_credits_available(user))

        confirm_reservation(str(first.id))
        confirm_reservation(str(first.id))
        user.refresh_from_db()
        self.assertEqual(user.credit_balance, 0)
        self.assertEqual(CreditTransaction.objects.filter(user=user).count(), 1)
        self.assertEqual(CreditReservation.objects.get(id=first.id).status, 'confirmed')

    def test_expired_reservation_cannot_be_confirmed(self):
        user = User.objects.create_user(
            email='expired@example.com',
            password='test-password',
            full_name='Reserva Expirada',
        )
        user.credit_balance = 2
        user.save(update_fields=['credit_balance'])
        reservation = reserve_credits(
            user, 2, str(user.id), 'stem_job', expires_in_seconds=-1
        )

        with self.assertRaises(ValueError):
            confirm_reservation(str(reservation.id))

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'released')
        user.refresh_from_db()
        self.assertEqual(user.credit_balance, 2)


def deduct_credits_available(user):
    from apps.credits.services.credit_service import check_balance
    return check_balance(user, required=1)
