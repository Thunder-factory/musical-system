import { ArrowLeft, CreditCard, Plus } from 'lucide-react'

import type { CreditPlan, PaymentMethod } from '../../api/client.service'
import { Button } from '../ui'

interface PaymentMethodsStepProps {
  plan: CreditPlan | null
  methods: PaymentMethod[]
  loading: boolean
  onBack: () => void
  onPay: (pm: PaymentMethod) => void
  onAddNewCard: () => void
}

export default function PaymentMethodsStep({
  plan,
  methods,
  loading,
  onBack,
  onPay,
  onAddNewCard,
}: PaymentMethodsStepProps) {
  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" leftIcon={<ArrowLeft size={14} />} onClick={onBack}>
        Volver a planes
      </Button>

      <p className="text-sm text-muted">
        {plan?.name} — <strong className="text-white">${plan?.price_usd}/mes</strong>
      </p>

      {loading ? (
        <p className="py-6 text-center text-sm text-muted">Cargando tarjetas...</p>
      ) : methods.length === 0 ? (
        <div className="py-8 text-center">
          <p className="mb-4 text-sm text-muted">No tienes tarjetas guardadas.</p>
          <Button leftIcon={<Plus size={15} />} onClick={onAddNewCard}>
            Agregar tarjeta
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {methods.map((pm) => (
            <div
              key={pm.id}
              className="flex items-center justify-between rounded-xl border border-border-strong bg-surface px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <CreditCard size={20} className="text-primary" aria-hidden="true" />
                <div>
                  <p className="text-sm font-semibold capitalize text-white">
                    {pm.brand} •••• {pm.last4}
                  </p>
                  <p className="text-xs text-muted">
                    Vence {pm.exp_month}/{pm.exp_year}
                  </p>
                </div>
              </div>
              <Button size="sm" onClick={() => onPay(pm)}>
                Pagar
              </Button>
            </div>
          ))}
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<Plus size={14} />}
            className="w-full"
            onClick={onAddNewCard}
          >
            Agregar nueva tarjeta
          </Button>
        </div>
      )}
    </div>
  )
}
