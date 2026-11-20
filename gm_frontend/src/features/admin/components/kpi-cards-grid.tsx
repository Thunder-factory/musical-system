import type { ReactNode } from 'react'
import { CreditCard, DollarSign, Music2, TrendingDown, TrendingUp, Users } from 'lucide-react'

import type { DashboardMetrics } from '../api/admin.api'

interface KpiItem {
  label: string
  value: string
  detail: string
  icon: ReactNode
}

export default function KpiCardsGrid({ metrics }: { metrics: DashboardMetrics }) {
  const items: KpiItem[] = [
    {
      label: 'Usuarios totales',
      value: metrics.total_users.toLocaleString('es-ES'),
      detail: `+${metrics.new_users_30d.toLocaleString('es-ES')} en los últimos 30 días`,
      icon: <Users size={16} aria-hidden="true" />,
    },
    {
      label: 'Ingresos del mes',
      value: `$${metrics.monthly_revenue_usd.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      detail: 'Pagos completados en el mes actual',
      icon: <DollarSign size={16} aria-hidden="true" />,
    },
    {
      label: 'Suscripciones activas',
      value: metrics.active_subscriptions.toLocaleString('es-ES'),
      detail: 'Cuentas con plan vigente',
      icon: <CreditCard size={16} aria-hidden="true" />,
    },
    {
      label: 'Canciones generadas',
      value: metrics.total_songs_generated.toLocaleString('es-ES'),
      detail: `${metrics.songs_last_30d.toLocaleString('es-ES')} en 30d · ${metrics.failed_jobs_30d} fallidos`,
      icon: <Music2 size={16} aria-hidden="true" />,
    },
    {
      label: 'Tasa de cancelación',
      value: `${metrics.churn_rate_pct.toFixed(1)}%`,
      detail: 'Cancelaciones últimos 30 días',
      icon: <TrendingDown size={16} aria-hidden="true" />,
    },
    {
      label: 'Ingresos anuales',
      value: `$${metrics.annual_revenue_usd.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      detail: `Acumulado del año ${new Date().getFullYear()}`,
      icon: <TrendingUp size={16} aria-hidden="true" />,
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <div
          key={item.label}
          className="flex flex-col gap-2.5 rounded-xl border border-border bg-card p-5"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">
              {item.label}
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-primary">
              {item.icon}
            </div>
          </div>
          <span className="text-2xl font-black tabular-nums text-white">{item.value}</span>
          <span className="text-xs text-muted">{item.detail}</span>
        </div>
      ))}
    </div>
  )
}
