import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'

export interface CreditPlan {
  id: number
  slug: string
  name: string
  credits_per_month: number
  price_usd: string
  features: string[]
  is_active: boolean
}

export interface PaymentMethod {
  id: number
  brand: string
  last4: string
  exp_month: number
  exp_year: number
  is_default: boolean
  created_at: string
  stripe_payment_method_id: string
}

export interface Payment {
  id: number
  amount: string
  currency: string
  stripe_payment_intent_id: string
  status: string
  created_at: string
}

export interface Subscription {
  id: string
  plan: CreditPlan
  status: string
  current_period_start: string
  current_period_end: string
}

export interface BalanceResponse {
  balance: number
  plan: CreditPlan | null
}

export const billingApi = {
  getBalance: () => client.get<BalanceResponse>(ENDPOINTS.credits.balance).then((r) => r.data),

  getPlans: () => client.get<CreditPlan[]>(ENDPOINTS.credits.plans).then((r) => r.data),

  getSubscriptions: () =>
    client.get<Subscription[]>(ENDPOINTS.credits.subscriptions).then((r) => r.data),

  getPaymentMethods: () =>
    client.get<PaymentMethod[]>(ENDPOINTS.credits.paymentMethods).then((r) => r.data),

  savePaymentMethod: (paymentMethodId: string) =>
    client
      .post<PaymentMethod>(ENDPOINTS.credits.paymentMethods, {
        payment_method_id: paymentMethodId,
      })
      .then((r) => r.data),

  deletePaymentMethod: (id: number) =>
    client.delete(ENDPOINTS.credits.paymentMethodDetail(id)).then((r) => r.data),

  getPayments: () => client.get<Payment[]>(ENDPOINTS.credits.pay).then((r) => r.data),

  changePassword: (payload: { old_password: string; new_password: string }) =>
    client.post<{ detail: string }>(ENDPOINTS.auth.changePassword, payload).then((r) => r.data),
}
