import { useState } from 'react'
import { CardElement, useElements, useStripe } from '@stripe/react-stripe-js'

import { Button } from '../../../components/ui'

function getCssToken(name: string, fallback: string): string {
  if (typeof document === 'undefined') {
    return fallback
  }
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

interface StripeAddCardFormProps {
  onSuccess: (paymentMethodId: string) => Promise<void>
  onCancel: () => void
}

export default function StripeAddCardForm({ onSuccess, onCancel }: StripeAddCardFormProps) {
  const stripe = useStripe()
  const elements = useElements()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    if (!stripe || !elements) {
      return
    }
    const cardEl = elements.getElement(CardElement)
    if (!cardEl) {
      return
    }
    setLoading(true)
    setError('')
    try {
      const { error: stripeErr, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: cardEl,
      })
      if (stripeErr) {
        setError(stripeErr.message ?? 'Error al validar la tarjeta.')
      } else if (paymentMethod) {
        await onSuccess(paymentMethod.id)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mt-4 flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
      <div className="rounded-lg border border-border-strong bg-surface px-4 py-3">
        <CardElement
          options={{
            style: {
              base: {
                fontSize: '14px',
                color: getCssToken('--text-base', '#f8fafc'),
                fontFamily: 'inherit',
                '::placeholder': { color: getCssToken('--text-placeholder', '#64748b') },
              },
              invalid: { color: getCssToken('--color-error', '#fb7185') },
            },
          }}
        />
      </div>
      {error && <p className="text-xs text-error">{error}</p>}
      <div className="flex gap-2">
        <Button
          variant="primary"
          size="sm"
          loading={loading}
          disabled={!stripe}
          onClick={() => void handleSubmit()}
        >
          {loading ? 'Agregando...' : 'Guardar tarjeta'}
        </Button>
        <Button variant="secondary" size="sm" onClick={onCancel} disabled={loading}>
          Cancelar
        </Button>
      </div>
    </div>
  )
}
