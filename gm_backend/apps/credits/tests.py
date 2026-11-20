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


class CreditPlanAdminTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.admin = User.objects.create_user(
            email='admin-plan@example.com',
            password='test-password',
            full_name='Admin Plan',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            email='user-plan@example.com',
            password='test-password',
            full_name='User Plan',
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.user_client = APIClient()
        self.user_client.force_authenticate(self.user)

    def test_admin_can_create_edit_and_list_all_plans_with_stripe_price_id(self):
        create_res = self.admin_client.post(
            '/api/credits/plans/',
            {
                'slug': 'studio',
                'name': 'Studio',
                'credits_per_month': 500,
                'price_usd': '49.99',
                'stripe_price_id': 'price_studio_123',
                'features': ['500 créditos/mes', 'Soporte VIP'],
                'is_active': False,
            },
            format='json',
        )
        self.assertEqual(create_res.status_code, 201, create_res.data)
        self.assertEqual(create_res.data['stripe_price_id'], 'price_studio_123')
        self.assertFalse(create_res.data['is_active'])

        plan_id = create_res.data['id']
        update_res = self.admin_client.put(
            f'/api/credits/plans/{plan_id}/',
            {'stripe_price_id': 'price_studio_456'},
            format='json',
        )
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.data['stripe_price_id'], 'price_studio_456')
        self.assertFalse(update_res.data['is_active'])

        # Usuario normal con ?all=1 no ve planes inactivos
        user_list = self.user_client.get('/api/credits/plans/?all=1')
        self.assertEqual(user_list.status_code, 200)
        self.assertEqual(user_list.data, [])

        # Admin con ?all=1 sí ve planes inactivos
        admin_all = self.admin_client.get('/api/credits/plans/?all=1')
        self.assertEqual(admin_all.status_code, 200)
        self.assertEqual(len(admin_all.data), 1)
        self.assertEqual(admin_all.data[0]['stripe_price_id'], 'price_studio_456')
