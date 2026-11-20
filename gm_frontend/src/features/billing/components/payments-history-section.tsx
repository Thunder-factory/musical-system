import { useMemo, useState } from 'react'
import { CreditCard } from 'lucide-react'

import { Badge, EmptyState, Select } from '../../../components/ui'
import type { Payment } from '../api/billing.api'
import MonthlySpendingChart from './monthly-spending-chart'

const MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

const STATUS_BADGE: Record<
  string,
  { variant: 'success' | 'error' | 'warning' | 'neutral'; label: string }
> = {
  succeeded: { variant: 'success', label: 'Exitoso' },
  paid: { variant: 'success', label: 'Exitoso' },
  requires_payment_method: { variant: 'error', label: 'Fallido' },
  failed: { variant: 'error', label: 'Fallido' },
  processing: { variant: 'warning', label: 'Procesando' },
}

export default function PaymentsHistorySection({ payments }: { payments: Payment[] }) {
  const currentYear = new Date().getFullYear()
  const [year, setYear] = useState(currentYear)
  const [month, setMonth] = useState<number | null>(null)

  const years = useMemo(() => {
    const set = new Set(payments.map((p) => new Date(p.created_at).getFullYear()))
    if (!set.has(currentYear)) {
      set.add(currentYear)
    }
    return [...set].sort((a, b) => b - a)
  }, [payments, currentYear])

  const chartData = useMemo(() => {
    const acc: Record<number, number> = {}
    payments
      .filter((p) => new Date(p.created_at).getFullYear() === year)
      .forEach((p) => {
        const m = new Date(p.created_at).getMonth()
        acc[m] = (acc[m] ?? 0) + parseFloat(p.amount)
      })
    return MONTHS.map((name, index) => ({ name, total: acc[index] ?? 0, index }))
  }, [payments, year])

  const filtered = useMemo(
    () =>
      payments.filter((p) => {
        const d = new Date(p.created_at)
        return d.getFullYear() === year && (month === null || d.getMonth() === month)
      }),
    [payments, year, month]
  )

  const totalFiltered = filtered.reduce((acc, p) => acc + parseFloat(p.amount), 0)

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-white">Historial de compras</h2>
        <div className="flex gap-2">
          <div className="w-28">
            <Select
              value={String(year)}
              onChange={(v) => {
                setYear(Number(v))
                setMonth(null)
              }}
              options={years.map((y) => ({ value: String(y), label: String(y) }))}
            />
          </div>
          <div className="w-44">
            <Select
              value={month === null ? '' : String(month)}
              onChange={(v) => setMonth(v === '' ? null : Number(v))}
              options={[
                { value: '', label: 'Todos los meses' },
                ...MONTHS.map((m, i) => ({ value: String(i), label: m })),
              ]}
            />
          </div>
        </div>
      </div>

      <MonthlySpendingChart
        year={year}
        data={chartData}
        selectedMonth={month}
        onSelectMonth={setMonth}
      />

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <p className="text-sm font-bold text-white">
            {month !== null ? `${MONTHS[month]} ${year}` : `Todo ${year}`}
            <span className="ml-2 text-xs font-normal text-muted">
              ({filtered.length} pago{filtered.length !== 1 ? 's' : ''})
            </span>
          </p>
          <p className="text-sm font-bold tabular-nums text-primary">
            ${totalFiltered.toFixed(2)} USD
          </p>
        </div>

        {filtered.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={<CreditCard size={22} />}
              title="Sin compras en este período"
              description="Cuando adquieras un plan o paquete de créditos aparecerá aquí."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-card-hover text-xs uppercase tracking-wider text-muted">
                  <th className="px-5 py-2.5 text-left">Fecha</th>
                  <th className="px-5 py-2.5 text-left">Monto</th>
                  <th className="px-5 py-2.5 text-left">Estado</th>
                  <th className="px-5 py-2.5 text-left">Referencia Stripe</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p, i) => {
                  const meta = STATUS_BADGE[p.status] ?? {
                    variant: 'neutral' as const,
                    label: p.status,
                  }
                  return (
                    <tr key={p.id} className={i % 2 === 0 ? 'bg-surface' : 'bg-night'}>
                      <td className="px-5 py-3 text-xs text-muted">
                        {new Date(p.created_at).toLocaleDateString('es-ES', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td className="px-5 py-3 font-bold tabular-nums text-white">
                        ${parseFloat(p.amount).toFixed(2)} {p.currency.toUpperCase()}
                      </td>
                      <td className="px-5 py-3">
                        <Badge variant={meta.variant}>{meta.label}</Badge>
                      </td>
                      <td className="max-w-[180px] truncate px-5 py-3 font-mono text-xs text-muted">
                        {p.stripe_payment_intent_id}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
