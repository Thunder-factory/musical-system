import { useCallback, useEffect, useState } from 'react'
import { RotateCw } from 'lucide-react'

import { Button } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { adminApi, type DashboardMetrics } from '../api/admin.api'
import KpiCardsGrid from '../components/kpi-cards-grid'
import MonthlyChartCard from '../components/monthly-chart-card'
import {
  PlansDistributionCard,
  RecentUsersCard,
} from '../components/plans-distribution-card'

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadMetrics = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setMetrics(await adminApi.getDashboardMetrics())
    } catch {
      const msg = 'No se pudieron cargar las métricas del dashboard.'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadMetrics()
  }, [loadMetrics])

  return (
    <div className="space-y-6 p-6 text-white">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black tracking-tight">Dashboard</h1>
          <p className="mt-0.5 text-xs text-muted">
            Métricas en tiempo real de MusicAI ({new Date().getFullYear()})
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<RotateCw size={14} />}
          loading={loading}
          onClick={() => void loadMetrics()}
        >
          Actualizar
        </Button>
      </header>

      {error && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          <span>{error}</span>
          <Button variant="secondary" size="sm" onClick={() => void loadMetrics()}>
            Reintentar
          </Button>
        </div>
      )}

      {loading && !metrics ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-card-hover" />
          ))}
        </div>
      ) : (
        metrics && (
          <>
            <KpiCardsGrid metrics={metrics} />
            <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
              <MonthlyChartCard series={metrics.monthly_series} />
              <PlansDistributionCard distribution={metrics.plans_distribution} />
            </div>
            <RecentUsersCard users={metrics.recent_users} />
          </>
        )
      )}
    </div>
  )
}
