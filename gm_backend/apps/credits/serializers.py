from rest_framework import serializers
from .models import CreditPlan, UserSubscription, CreditTransaction, Payment, PaymentMethod


class CreditPlanSerializer(serializers.ModelSerializer):
    stripe_price_id = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=''
    )
    features = serializers.JSONField(required=False, default=list)
    is_active = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = CreditPlan
        fields = [
            'id',
            'slug',
            'name',
            'credits_per_month',
            'price_usd',
            'stripe_price_id',
            'features',
            'is_active',
        ]


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = CreditPlanSerializer(read_only=True)

    class Meta:
        model  = UserSubscription
        fields = ['id', 'plan', 'status', 'current_period_start', 'current_period_end', 'created_at']


class CreditTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CreditTransaction
        fields = ['id', 'amount', 'balance_after', 'type', 'description', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Payment
        fields = ['id', 'amount', 'currency', 'stripe_payment_intent_id', 'status', 'created_at']


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PaymentMethod
        fields = ['id', 'brand', 'last4', 'exp_month', 'exp_year', 'is_default', 'created_at', 'stripe_payment_method_id']
