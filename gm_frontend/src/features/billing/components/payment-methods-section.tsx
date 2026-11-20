import { useCallback, useEffect, useState } from 'react'
import { Elements } from '@stripe/react-stripe-js'
import type { Stripe } from '@stripe/stripe-js'
import { CreditCard, Plus, Trash2 } from 'lucide-react'

import { Button, useConfirm } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { billingApi, type PaymentMethod } from '../api/billing.api'
import StripeAddCardForm from './stripe-add-card-form'

export default function PaymentMethodsSection() {
  const confirm = useConfirm()
  const [methods, setMethods] = useState<PaymentMethod[]>([])
  const [loading, setLoading] = useState(true)
  const [addingCard, setAddingCard] = useState(false)
  const [stripePromise, setStripePromise] = useState<Promise<Stripe | null> | null>(null)
  const stripeKey = import.meta.env.VITE_STRIPE_PUBLIC_KEY ?? ''

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setMethods(await billingApi.getPaymentMethods())
    } catch {
      toast.error('No se pudieron cargar tus métodos de pago')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!addingCard || stripePromise || !stripeKey) {
      return
    }
    setStripePromise(import('@stripe/stripe-js').then(({ loadStripe }) => loadStripe(stripeKey)))
  }, [addingCard, stripePromise, stripeKey])

  async function handleCardAdded(pmId: string) {
    try {
      const saved = await billingApi.savePaymentMethod(pmId)
      setMethods((prev) => [...prev, saved])
      setAddingCard(false)
      toast.success('Tarjeta guardada correctamente')
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Error al guardar la tarjeta.'
      toast.error('No se pudo guardar la tarjeta', msg)
    }
  }

  async function handleRemove(method: PaymentMethod) {
    const accepted = await confirm({
      title: '¿Eliminar tarjeta?',
      description: `Se eliminará la tarjeta ${method.brand.toUpperCase()} terminada en ${method.last4}.`,
      confirmLabel: 'Eliminar tarjeta',
      variant: 'danger',
    })
    if (!accepted) {
      return
    }
    try {
      await billingApi.deletePaymentMethod(method.id)
      setMethods((prev) => prev.filter((m) => m.id !== method.id))
      toast.success('Tarjeta eliminada')
    } catch {
      toast.error('No se pudo eliminar la tarjeta')
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-white">Métodos de pago</h2>
          <p className="mt-0.5 text-xs text-muted">
            Administra las tarjetas guardadas para tus suscripciones y recargas.
          </p>
        </div>

        <Button
          variant={addingCard ? 'danger' : 'secondary'}
          size="sm"
          leftIcon={!addingCard ? <Plus size={14} /> : undefined}
          onClick={() => setAddingCard((v) => !v)}
        >
          {addingCard ? 'Cancelar' : 'Agregar tarjeta'}
        </Button>
      </div>

      {addingCard &&
        (!stripeKey || !stripePromise ? (
          <p className="mb-4 rounded-lg border border-error-border bg-error-soft p-3 text-xs text-error">
            Falta configurar la clave pública de Stripe (VITE_STRIPE_PUBLIC_KEY).
          </p>
        ) : (
          <Elements stripe={stripePromise}>
            <StripeAddCardForm onSuccess={handleCardAdded} onCancel={() => setAddingCard(false)} />
          </Elements>
        ))}

      {loading ? (
        <p className="py-3 text-sm text-muted">Cargando tarjetas...</p>
      ) : methods.length === 0 && !addingCard ? (
        <p className="py-2 text-sm text-muted">No tienes tarjetas guardadas.</p>
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          {methods.map((m) => (
            <div
              key={m.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <CreditCard size={18} className="shrink-0 text-primary" aria-hidden="true" />
                <div>
                  <p className="text-sm font-semibold capitalize text-white">
                    {m.brand} •••• {m.last4}
                  </p>
                  <p className="text-xs text-muted">
                    Vence {m.exp_month}/{m.exp_year}
                  </p>
                </div>
              </div>
              <Button
                variant="danger"
                size="sm"
                leftIcon={<Trash2 size={13} />}
                onClick={() => void handleRemove(m)}
              >
                Eliminar
              </Button>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
