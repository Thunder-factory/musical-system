import { useCallback, useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import { Badge, Button, useConfirm } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { adminApi, type CreditPlan, type StripePrice } from '../api/admin.api'
import PlanFormModal, { type PlanPayload } from '../components/plan-form-modal'
import StripePricesTab from '../components/stripe-prices-tab'

export default function PlanesPage() {
  const confirm = useConfirm()
  const [plans, setPlans] = useState<CreditPlan[]>([])
  const [prices, setPrices] = useState<StripePrice[]>([])
  const [tab, setTab] = useState<'plans' | 'stripe'>('plans')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<CreditPlan | null>(null)
  const [savingPlan, setSavingPlan] = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([adminApi.getPlans(true), adminApi.getStripePrices()])
      setPlans(p)
      setPrices(s)
    } catch {
      toast.error('No se pudieron cargar los planes y precios')
    }
  }, [])

  useEffect(() => {
    void fetchAll()
  }, [fetchAll])

  async function handleSavePlan(payload: PlanPayload) {
    setSavingPlan(true)
    try {
      if (editingPlan) {
        await adminApi.updatePlan(editingPlan.id, payload)
        toast.success('Plan actualizado')
      } else {
        await adminApi.createPlan(payload)
        toast.success('Plan creado')
      }
      setModalOpen(false)
      setEditingPlan(null)
      setPlans(await adminApi.getPlans(true))
    } catch {
      toast.error('Error al guardar el plan')
    } finally {
      setSavingPlan(false)
    }
  }

  async function handleDeletePlan(plan: CreditPlan) {
    const accepted = await confirm({
      title: '¿Eliminar plan?',
      description: `Se eliminará el plan "${plan.name}". Esta acción no se puede deshacer.`,
      confirmLabel: 'Eliminar',
      variant: 'danger',
    })
    if (!accepted) {
      return
    }
    try {
      await adminApi.deletePlan(plan.id)
      setPlans((prev) => prev.filter((p) => p.id !== plan.id))
      toast.success('Plan eliminado')
    } catch {
      toast.error('No se pudo eliminar el plan')
    }
  }

  return (
    <div className="space-y-6 p-6 text-white">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Gestión de planes</h1>
          <p className="mt-1 text-sm text-muted">
            Administra los planes de suscripción y precios de Stripe.
          </p>
        </div>

        {tab === 'plans' && (
          <Button
            variant="primary"
            leftIcon={<Plus size={15} />}
            onClick={() => {
              setEditingPlan(null)
              setModalOpen(true)
            }}
          >
            Nuevo plan
          </Button>
        )}
      </header>

      <div className="flex gap-2">
        {(
          [
            ['plans', 'Planes'],
            ['stripe', 'Stripe Prices'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`rounded-lg px-4 py-2 text-sm font-bold transition-colors ${
              tab === key
                ? 'bg-primary text-black'
                : 'bg-card-hover text-muted hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'plans' ? (
        <div className="overflow-x-auto rounded-xl border border-border bg-card">
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="bg-card-hover text-xs uppercase tracking-wider text-muted">
                <th className="px-4 py-3 text-left">Plan</th>
                <th className="px-4 py-3 text-left">Precio</th>
                <th className="px-4 py-3 text-left">Créditos/mes</th>
                <th className="px-4 py-3 text-left">Estado</th>
                <th className="px-4 py-3 text-left">Stripe ID</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((plan, i) => (
                <tr key={plan.id} className={i % 2 === 0 ? 'bg-surface' : 'bg-night'}>
                  <td className="px-4 py-3">
                    <p className="font-semibold text-white">{plan.name}</p>
                    <p className="font-mono text-xs text-muted">{plan.slug}</p>
                  </td>
                  <td className="px-4 py-3 tabular-nums text-muted">${plan.price_usd}</td>
                  <td className="px-4 py-3 tabular-nums">{plan.credits_per_month}</td>
                  <td className="px-4 py-3">
                    <Badge variant={plan.is_active ? 'success' : 'neutral'}>
                      {plan.is_active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td className="max-w-[160px] truncate px-4 py-3 font-mono text-xs text-muted">
                    {plan.stripe_price_id || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1.5">
                      <Button
                        variant="secondary"
                        size="sm"
                        leftIcon={<Pencil size={13} />}
                        onClick={() => {
                          setEditingPlan(plan)
                          setModalOpen(true)
                        }}
                      >
                        Editar
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        leftIcon={<Trash2 size={13} />}
                        onClick={() => void handleDeletePlan(plan)}
                      >
                        Eliminar
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {plans.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-muted">
                    No hay planes registrados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <StripePricesTab
          prices={prices}
          onReload={async () => setPrices(await adminApi.getStripePrices())}
        />
      )}

      <PlanFormModal
        open={modalOpen}
        editingPlan={editingPlan}
        saving={savingPlan}
        onClose={() => {
          setModalOpen(false)
          setEditingPlan(null)
        }}
        onSubmit={handleSavePlan}
      />
    </div>
  )
}
