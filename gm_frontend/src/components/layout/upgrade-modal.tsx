import { lazy, Suspense, useEffect, useState } from 'react'
import { ArrowLeft, LoaderCircle } from 'lucide-react'
import type { Stripe } from '@stripe/stripe-js'

import { authService } from '../../api/auth-service'
import { clientService, type CreditPlan, type PaymentMethod } from '../../api/client.service'
import { useAuthStore } from '../../store/auth.store'
import { Button, Modal } from '../ui'
import PaymentMethodsStep from './payment-methods-step'
import PlanCard from './plan-card'
import UpgradeStatusView from './upgrade-status-view'

const LazyStripeCardForm = lazy(() => import('./stripe-card-form'))
type Step = 'plans' | 'payment-methods' | 'new-card' | 'processing' | 'success' | 'error'

const STEP_TITLES: Record<Step, string> = {
  plans: 'Elige tu plan',
  'payment-methods': 'Selecciona una tarjeta',
  'new-card': 'Agregar tarjeta',
  processing: 'Procesando pago',
  success: '¡Pago exitoso!',
  error: 'Error en el pago',
}

interface UpgradeModalProps {
  show: boolean
  currentPlanSlug?: string | null
  onClose: () => void
  onSuccess: (planName: string) => void
}

export default function UpgradeModal({ show, currentPlanSlug, onClose, onSuccess }: UpgradeModalProps) {
  const setUser = useAuthStore((state) => state.setUser)
  const [step, setStep] = useState<Step>('plans')
  const [plans, setPlans] = useState<CreditPlan[]>([])
  const [plansError, setPlansError] = useState('')
  const [methods, setMethods] = useState<PaymentMethod[]>([])
  const [selectedPlan, setSelectedPlan] = useState<CreditPlan | null>(null)
  const [loadingPlans, setLoadingPlans] = useState(false)
  const [loadingMethods, setLoadingMethods] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [stripePromise, setStripePromise] = useState<Promise<Stripe | null> | null>(null)
  const stripeKey = import.meta.env.VITE_STRIPE_PUBLIC_KEY ?? ''

  useEffect(() => {
    if (!show) {
      return
    }
    let cancelled = false
    setLoadingPlans(true)
    setPlansError('')
    clientService
      .getPlans()
      .then((data) => !cancelled && setPlans(data.filter((plan) => plan.is_active !== false)))
      .catch(() => !cancelled && setPlansError('No se pudieron cargar los planes disponibles.'))
      .finally(() => !cancelled && setLoadingPlans(false))
    return () => {
      cancelled = true
    }
  }, [show])

  useEffect(() => {
    if (step !== 'new-card' || stripePromise || !stripeKey) {
      return
    }
    setStripePromise(import('@stripe/stripe-js').then(({ loadStripe }) => loadStripe(stripeKey)))
  }, [step, stripePromise, stripeKey])

  async function handleSelectPlan(plan: CreditPlan) {
    setSelectedPlan(plan)
    setStep('payment-methods')
    setLoadingMethods(true)
    try {
      setMethods(await clientService.getPaymentMethods())
    } catch {
      setMethods([])
    } finally {
      setLoadingMethods(false)
    }
  }

  async function handleCardAdded(pmId: string) {
    setLoadingMethods(true)
    try {
      await clientService.savePaymentMethod(pmId)
      setMethods(await clientService.getPaymentMethods())
      setStep('payment-methods')
    } catch (err: unknown) {
      setErrorMsg((err as { message?: string })?.message ?? 'No se pudo agregar la tarjeta.')
      setStep('error')
    } finally {
      setLoadingMethods(false)
    }
  }

  async function handlePay(pm: PaymentMethod) {
    if (!selectedPlan) {
      return
    }
    setStep('processing')
    try {
      await clientService.makePayment(pm.stripe_payment_method_id, parseFloat(selectedPlan.price_usd), selectedPlan.slug)
      setUser(await authService.getProfile())
      onSuccess(selectedPlan.name.toUpperCase())
      setStep('success')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setErrorMsg(detail ?? 'Error al procesar el pago.')
      setStep('error')
    }
  }

  function handleClose() {
    if (step === 'processing') {
      return
    }
    onClose()
    setStep('plans')
    setSelectedPlan(null)
    setErrorMsg('')
  }

  const recommendedId = plans.find((p) => p.slug === 'pro')?.id ?? plans.find((p) => Number(p.price_usd) > 0)?.id

  return (
    <Modal open={show} onClose={handleClose} title={STEP_TITLES[step]} size="xl" preventClose={step === 'processing'}>
      {step === 'plans' && (
        <div className="space-y-5">
          <p className="text-sm text-muted">Desbloquea todo el potencial de MusicAI con créditos mensuales.</p>
          {loadingPlans ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted">
              <LoaderCircle size={18} className="animate-spin text-primary" aria-hidden="true" />
              <span>Cargando planes...</span>
            </div>
          ) : plansError ? (
            <p className="py-6 text-center text-sm text-error">{plansError}</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {plans.map((plan) => (
                <PlanCard key={plan.id} plan={plan} isRecommended={plan.id === recommendedId} isCurrent={currentPlanSlug ? plan.slug === currentPlanSlug : Number(plan.price_usd) <= 0} onSelect={handleSelectPlan} />
              ))}
            </div>
          )}
        </div>
      )}
      {step === 'payment-methods' && (
        <PaymentMethodsStep plan={selectedPlan} methods={methods} loading={loadingMethods} onBack={() => setStep('plans')} onPay={handlePay} onAddNewCard={() => setStep('new-card')} />
      )}
      {step === 'new-card' && (
        <div className="space-y-4">
          <Button variant="ghost" size="sm" leftIcon={<ArrowLeft size={14} />} onClick={() => setStep('payment-methods')}>Volver</Button>
          <p className="text-xs text-muted">Tus datos están protegidos por Stripe.</p>
          {!stripeKey || !stripePromise ? (
            <p className="rounded-lg border border-error-border bg-error-soft p-3 text-xs text-error">Falta configurar la clave pública de Stripe (VITE_STRIPE_PUBLIC_KEY).</p>
          ) : (
            <Suspense fallback={<p className="py-6 text-center text-sm text-muted">Cargando formulario seguro...</p>}>
              <LazyStripeCardForm stripePromise={stripePromise} onSuccess={handleCardAdded} onCancel={() => setStep('payment-methods')} />
            </Suspense>
          )}
        </div>
      )}
      {(step === 'processing' || step === 'success' || step === 'error') && (
        <UpgradeStatusView status={step} errorMsg={errorMsg} onRetry={() => setStep('payment-methods')} onClose={handleClose} />
      )}
    </Modal>
  )
}
