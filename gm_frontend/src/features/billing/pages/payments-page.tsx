import { useCallback, useEffect, useMemo, useState } from 'react'
import { Coins, CreditCard, Sparkles } from 'lucide-react'

import UpgradeModal from '../../../components/layout/upgrade-modal'
import { Badge, Button } from '../../../components/ui'
import { refreshAuthBalance } from '../../../store/active-jobs.store'
import { useAuthStore } from '../../../store/auth.store'
import { toast } from '../../../store/toast.store'
import { billingApi, type Payment, type Subscription } from '../api/billing.api'
import PaymentMethodsSection from '../components/payment-methods-section'
import PaymentsHistorySection from '../components/payments-history-section'

export default function PaymentsPage() {
  const user = useAuthStore((s) => s.user)
  const [payments, setPayments] = useState<Payment[]>([])
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showUpgrade, setShowUpgrade] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [payData, subData] = await Promise.all([
        billingApi.getPayments(),
        billingApi.getSubscriptions().catch(() => [] as Subscription[]),
      ])
      setPayments(payData)
      setSubscriptions(subData)
    } catch {
      setError('No se pudo cargar tu información de pagos.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const activeSub = useMemo(
    () => subscriptions.find((s) => s.status === 'active') ?? null,
    [subscriptions]
  )

  if (loading) {
    return <div className="px-8 py-7 text-sm text-muted">Cargando pagos y plan...</div>
  }

  return (
    <div className="min-h-full space-y-6 px-6 pb-20 pt-7 text-white sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Pagos y plan</h1>
          <p className="mt-1 text-sm text-muted">
            Administra tu suscripción, saldo de créditos, tarjetas e historial de compras.
          </p>
        </div>
        <Button
          variant="primary"
          leftIcon={<Sparkles size={15} />}
          onClick={() => setShowUpgrade(true)}
        >
          Mejorar plan / Comprar créditos
        </Button>
      </header>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          {error}
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-2">
        <div className="flex items-center justify-between rounded-xl border border-border bg-card p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">Plan actual</p>
            <div className="mt-1.5 flex items-center gap-2.5">
              <p className="text-2xl font-black text-white">{activeSub?.plan?.name ?? 'Free'}</p>
              <Badge variant={activeSub ? 'primary' : 'neutral'}>
                {activeSub ? 'Activo' : 'Básico'}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted">
              {activeSub
                ? `${activeSub.plan.credits_per_month} créditos mensuales`
                : 'Actualiza tu plan para recibir créditos cada mes'}
            </p>
          </div>
          <CreditCard size={28} className="text-primary/80" aria-hidden="true" />
        </div>

        <div className="flex items-center justify-between rounded-xl border border-border bg-card p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">
              Saldo de créditos
            </p>
            <p className="mt-1.5 text-2xl font-black tabular-nums text-primary">
              {user?.credit_balance ?? 0}
            </p>
            <p className="mt-1 text-xs text-muted">
              Disponibles para canciones, karaoke, stems, traducciones y mix
            </p>
          </div>
          <Coins size={28} className="text-primary/80" aria-hidden="true" />
        </div>
      </section>

      <PaymentMethodsSection />
      <PaymentsHistorySection payments={payments} />

      <UpgradeModal
        show={showUpgrade}
        currentPlanSlug={activeSub?.plan?.slug ?? null}
        onClose={() => setShowUpgrade(false)}
        onSuccess={(planName) => {
          toast.success('¡Plan actualizado!', `Ahora estás en el plan ${planName}.`)
          void refreshAuthBalance()
          void loadData()
        }}
      />
    </div>
  )
}
