from datetime import timedelta
from decimal import Decimal
import uuid

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.credits.models import CreditPlan, Payment, UserSubscription
from apps.songs.models import GenerationJob, Song
from apps.users.models import Role, User, UserRole


class ReportsAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin-reports@example.com',
            password='test-password',
            full_name='Admin Reports',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            email='normal-reports@example.com',
            password='test-password',
            full_name='Usuario Normal',
            credit_balance=10,
        )
        self.other = User.objects.create_user(
            email='pro-reports@example.com',
            password='test-password',
            full_name='Usuario Pro',
            credit_balance=50,
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.user_client = APIClient()
        self.user_client.force_authenticate(self.user)

    def test_dashboard_requires_admin(self):
        self.assertEqual(self.user_client.get('/api/reports/dashboard/').status_code, 403)
        self.assertEqual(APIClient().get('/api/reports/dashboard/').status_code, 401)

    def test_dashboard_returns_real_metrics_from_postgres(self):
        now = timezone.now()
        last_45 = now - timedelta(days=45)

        free_plan = CreditPlan.objects.create(
            slug='free', name='Free', credits_per_month=5, price_usd=Decimal('0.00'), is_active=True
        )
        pro_plan = CreditPlan.objects.create(
            slug='pro', name='Pro', credits_per_month=100, price_usd=Decimal('19.99'), is_active=True
        )
        UserSubscription.objects.create(user=self.other, plan=pro_plan, status='active')
        canceled = UserSubscription.objects.create(user=self.user, plan=pro_plan, status='canceled')
        UserSubscription.objects.filter(id=canceled.id).update(updated_at=now - timedelta(days=2))

        Payment.objects.create(
            user=self.other, amount=Decimal('19.99'), currency='usd',
            stripe_payment_intent_id='pi_1', status='succeeded',
        )
        Payment.objects.create(
            user=self.other, amount=Decimal('10.01'), currency='usd',
            stripe_payment_intent_id='pi_2', status='paid',
        )
        Payment.objects.create(
            user=self.other, amount=Decimal('99.00'), currency='usd',
            stripe_payment_intent_id='pi_fail', status='failed',
        )

        song_recent = Song.objects.create(user=self.other, title='Reciente', status='ready')
        song_old = Song.objects.create(user=self.other, title='Antigua', status='ready')
        Song.objects.filter(id=song_old.id).update(created_at=last_45)
        GenerationJob.objects.create(user=self.other, song=song_recent, mode='from_description', status='failed')

        response = self.admin_client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, 200)
        data = response.data

        self.assertEqual(data['total_users'], 3)
        self.assertEqual(data['new_users_30d'], 3)
        self.assertEqual(data['active_subscriptions'], 1)
        self.assertEqual(data['total_songs_generated'], 2)
        self.assertEqual(data['songs_last_30d'], 1)
        self.assertEqual(data['failed_jobs_30d'], 1)
        self.assertEqual(data['monthly_revenue_usd'], 30.0)
        self.assertEqual(data['annual_revenue_usd'], 30.0)
        self.assertEqual(data['churn_rate_pct'], 50.0)

        self.assertEqual(len(data['monthly_series']), 12)
        self.assertEqual(data['monthly_series'][0]['label'], 'Ene')
        self.assertEqual(data['monthly_series'][-1]['label'], 'Dic')
        current_month_item = data['monthly_series'][now.month - 1]
        self.assertEqual(current_month_item['revenue_usd'], 30.0)
        self.assertEqual(current_month_item['new_users'], 3)

        dist_by_slug = {item['slug']: item for item in data['plans_distribution']}
        self.assertEqual(dist_by_slug[free_plan.slug]['users_count'], 2)
        self.assertEqual(dist_by_slug['pro']['users_count'], 1)

        self.assertEqual(len(data['recent_users']), 3)
        recent_by_email = {u['email']: u for u in data['recent_users']}
        self.assertEqual(recent_by_email['pro-reports@example.com']['plan_name'], 'Pro')
        self.assertEqual(recent_by_email['normal-reports@example.com']['plan_name'], 'Free')

    def test_users_list_includes_plan_name_and_supports_search(self):
        pro_plan = CreditPlan.objects.create(
            slug='pro', name='Pro', credits_per_month=100, price_usd=Decimal('19.99'), is_active=True
        )
        UserSubscription.objects.create(user=self.other, plan=pro_plan, status='active')

        response = self.admin_client.get('/api/reports/users/?search=pro-reports')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['email'], 'pro-reports@example.com')
        self.assertEqual(response.data[0]['plan_name'], 'Pro')
        self.assertEqual(response.data[0]['credit_balance'], 50)

    def test_admin_can_update_other_user_and_audit_is_logged(self):
        response = self.admin_client.patch(
            f'/api/reports/users/{self.user.id}/',
            {'is_staff': True, 'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)
        self.assertFalse(self.user.is_active)
        self.assertTrue(UserRole.objects.filter(user=self.user, role__name='admin').exists())
        self.assertTrue(
            AuditLog.objects.filter(
                user=self.admin,
                action='admin.user.update',
                resource_type='user',
                resource_id=str(self.user.id),
            ).exists()
        )

    def test_admin_cannot_demote_or_deactivate_self(self):
        demote = self.admin_client.patch(
            f'/api/reports/users/{self.admin.id}/',
            {'is_staff': False},
            format='json',
        )
        deactivate = self.admin_client.patch(
            f'/api/reports/users/{self.admin.id}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(demote.status_code, 400)
        self.assertEqual(deactivate.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_active)

    def test_non_admin_cannot_update_users_and_missing_user_returns_404(self):
        forbidden = self.user_client.patch(
            f'/api/reports/users/{self.other.id}/',
            {'is_staff': True},
            format='json',
        )
        missing = self.admin_client.patch(
            f'/api/reports/users/{uuid.uuid4()}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(missing.status_code, 404)
