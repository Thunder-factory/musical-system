import { useState, type FormEvent } from 'react'

import { Badge, Button, FormField, Input, Select, useConfirm } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { adminApi, type StripePrice } from '../api/admin.api'

interface StripePricesTabProps {
  prices: StripePrice[]
  onReload: () => Promise<void>
}

export default function StripePricesTab({ prices, onReload }: StripePricesTabProps) {
  const confirm = useConfirm()
  const [name, setName] = useState('')
  const [priceUsd, setPriceUsd] = useState('0')
  const [interval, setInterval] = useState<'month' | 'year'>('month')
  const [creating, setCreating] = useState(false)

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      return
    }
    setCreating(true)
    try {
      const res = await adminApi.createStripePrice({
        name: name.trim(),
        price_usd: Number(priceUsd) || 0,
        interval,
      })
      toast.success('Precio creado en Stripe', `ID: ${res.stripe_price_id}`)
      setName('')
      setPriceUsd('0')
      await onReload()
    } catch {
      toast.error('No se pudo crear el precio en Stripe')
    } finally {
      setCreating(false)
    }
  }

  async function handleDeactivate(priceId: string) {
    const accepted = await confirm({
      title: '¿Desactivar precio en Stripe?',
      description: `El precio ${priceId} dejará de estar activo para nuevas suscripciones.`,
      confirmLabel: 'Desactivar',
      variant: 'danger',
    })
    if (!accepted) {
      return
    }
    try {
      await adminApi.deleteStripePrice(priceId)
      await onReload()
      toast.success('Precio desactivado en Stripe')
    } catch {
      toast.error('No se pudo desactivar el precio')
    }
  }

  return (
    <div className="space-y-6">
      <form
        onSubmit={handleCreate}
        className="grid max-w-lg gap-3 rounded-xl border border-border bg-card p-5"
      >
        <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
          Crear Stripe Price
        </h2>
        <FormField label="Nombre del producto" required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ej: Plan Pro"
          />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Precio (USD)" required>
            <Input
              type="number"
              step="0.01"
              value={priceUsd}
              onChange={(e) => setPriceUsd(e.target.value)}
            />
          </FormField>
          <Select
            label="Intervalo"
            value={interval}
            onChange={(v) => setInterval(v as 'month' | 'year')}
            options={[
              { value: 'month', label: 'Mensual' },
              { value: 'year', label: 'Anual' },
            ]}
          />
        </div>
        <Button
          type="submit"
          variant="primary"
          loading={creating}
          disabled={!name.trim()}
          className="w-fit"
        >
          Crear en Stripe
        </Button>
      </form>

      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className="w-full min-w-[600px] text-sm">
          <thead>
            <tr className="bg-card-hover text-xs uppercase tracking-wider text-muted">
              <th className="px-4 py-3 text-left">Price ID</th>
              <th className="px-4 py-3 text-left">Monto</th>
              <th className="px-4 py-3 text-left">Intervalo</th>
              <th className="px-4 py-3 text-left">Estado</th>
              <th className="px-4 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {prices.map((sp, i) => (
              <tr key={sp.price_id} className={i % 2 === 0 ? 'bg-surface' : 'bg-night'}>
                <td className="px-4 py-3 font-mono text-xs text-muted">{sp.price_id}</td>
                <td className="px-4 py-3 tabular-nums">
                  ${(sp.amount / 100).toFixed(2)} {sp.currency.toUpperCase()}
                </td>
                <td className="px-4 py-3 capitalize">{sp.interval}</td>
                <td className="px-4 py-3">
                  <Badge variant={sp.active ? 'success' : 'error'}>
                    {sp.active ? 'Activo' : 'Inactivo'}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  <Button
                    variant="danger"
                    size="sm"
                    disabled={!sp.active}
                    onClick={() => void handleDeactivate(sp.price_id)}
                  >
                    Desactivar
                  </Button>
                </td>
              </tr>
            ))}
            {prices.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted">
                  No hay precios en Stripe.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
