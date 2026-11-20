import { useState } from 'react'
import { CardElement, Elements, useElements, useStripe } from '@stripe/react-stripe-js'
import type { Stripe } from '@stripe/stripe-js'

import { Button } from '../ui'

interface StripeCardFormProps {
  stripePromise: Promise<Stripe | null>
  onSuccess: (paymentMethodId: string) => void
  onCancel: () => void
}

function getCssToken(name: string, fallback: string): string {
  if (typeof document === 'undefined') {
    return fallback
  }
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function CardFields({
  onSuccess,
  onCancel,
}: {
  onSuccess: (paymentMethodId: string) => void
  onCancel: () => void
}) {
  const stripe = useStripe()
  const elements = useElements()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    if (!stripe || !elements) {
      return
    }
    const cardElement = elements.getElement(CardElement)
    if (!cardElement) {
      return
    }

    setLoading(true)
    setError('')
    try {
      const { error: stripeErr, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: cardElement,
      })
      if (stripeErr) {
        setError(stripeErr.message ?? 'Error al agregar la tarjeta.')
      } else if (paymentMethod) {
        onSuccess(paymentMethod.id)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-border-strong bg-surface px-4 py-3.5">
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

      <Button onClick={handleSubmit} loading={loading} disabled={!stripe} className="w-full">
        {loading ? 'Agregando...' : 'Guardar tarjeta'}
      </Button>
      <Button variant="ghost" size="sm" onClick={onCancel} className="w-full">
        Cancelar
      </Button>
    </div>
  )
}

export default function StripeCardForm({ stripePromise, onSuccess, onCancel }: StripeCardFormProps) {
  return (
    <Elements stripe={stripePromise}>
      <CardFields onSuccess={onSuccess} onCancel={onCancel} />
    </Elements>
  )
}
