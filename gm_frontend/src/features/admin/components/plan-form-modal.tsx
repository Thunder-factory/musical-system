import { useEffect, useState, type FormEvent } from 'react'

import { Button, FormField, Input, Modal, Textarea } from '../../../components/ui'
import type { CreditPlan } from '../api/admin.api'

export type PlanPayload = Omit<CreditPlan, 'id'>

interface PlanFormModalProps {
  open: boolean
  editingPlan: CreditPlan | null
  saving: boolean
  onClose: () => void
  onSubmit: (payload: PlanPayload) => Promise<void>
}

export default function PlanFormModal({
  open,
  editingPlan,
  saving,
  onClose,
  onSubmit,
}: PlanFormModalProps) {
  const [slug, setSlug] = useState('')
  const [name, setName] = useState('')
  const [creditsPerMonth, setCreditsPerMonth] = useState('0')
  const [priceUsd, setPriceUsd] = useState('0.00')
  const [stripePriceId, setStripePriceId] = useState('')
  const [featuresText, setFeaturesText] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      return
    }
    setError(null)
    if (editingPlan) {
      setSlug(editingPlan.slug)
      setName(editingPlan.name)
      setCreditsPerMonth(String(editingPlan.credits_per_month))
      setPriceUsd(editingPlan.price_usd)
      setStripePriceId(editingPlan.stripe_price_id ?? '')
      setFeaturesText((editingPlan.features ?? []).join('\n'))
      setIsActive(editingPlan.is_active)
    } else {
      setSlug('')
      setName('')
      setCreditsPerMonth('0')
      setPriceUsd('0.00')
      setStripePriceId('')
      setFeaturesText('')
      setIsActive(true)
    }
  }, [open, editingPlan])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!slug.trim() || !name.trim()) {
      setError('Completa el slug y el nombre del plan.')
      return
    }
    const parsedCredits = Number(creditsPerMonth)
    if (!Number.isFinite(parsedCredits) || parsedCredits < 0) {
      setError('Los créditos mensuales deben ser un número válido.')
      return
    }
    setError(null)
    const features = featuresText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    await onSubmit({
      slug: slug.trim(),
      name: name.trim(),
      credits_per_month: parsedCredits,
      price_usd: priceUsd.trim() || '0.00',
      stripe_price_id: stripePriceId.trim(),
      features,
      is_active: isActive,
    })
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editingPlan ? `Editar plan: ${editingPlan.name}` : 'Nuevo plan'}
      size="md"
      preventClose={saving}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Slug" required>
            <Input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="ej: pro"
              disabled={saving}
            />
          </FormField>

          <FormField label="Nombre" required>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ej: Pro"
              disabled={saving}
            />
          </FormField>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Créditos / mes" required>
            <Input
              type="number"
              min={0}
              value={creditsPerMonth}
              onChange={(e) => setCreditsPerMonth(e.target.value)}
              disabled={saving}
            />
          </FormField>

          <FormField label="Precio USD" required>
            <Input
              value={priceUsd}
              onChange={(e) => setPriceUsd(e.target.value)}
              placeholder="9.00"
              disabled={saving}
            />
          </FormField>
        </div>

        <FormField label="Stripe Price ID">
          <Input
            value={stripePriceId}
            onChange={(e) => setStripePriceId(e.target.value)}
            placeholder="price_xxx"
            disabled={saving}
          />
        </FormField>

        <FormField
          label="Beneficios (uno por línea)"
          hint="Cada línea aparecerá como viñeta en la tarjeta del plan."
        >
          <Textarea
            value={featuresText}
            onChange={(e) => setFeaturesText(e.target.value)}
            placeholder={'100 créditos mensuales\nExportación en WAV sin pérdida\nPrioridad en cola'}
            rows={4}
            disabled={saving}
          />
        </FormField>

        <label className="flex cursor-pointer items-center gap-2.5 text-sm text-white">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            disabled={saving}
            className="h-4 w-4 accent-primary"
          />
          <span>Plan activo y visible para clientes</span>
        </label>

        {error && (
          <p role="alert" className="text-xs text-error">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={saving}>
            {saving ? 'Guardando...' : editingPlan ? 'Actualizar plan' : 'Crear plan'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
