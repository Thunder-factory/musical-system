import { useState } from 'react'

import type { MonthlySeriesPoint } from '../api/admin.api'

type MetricKey = 'revenue_usd' | 'new_users' | 'songs_generated'

const TABS: Array<{
  key: MetricKey
  tabLabel: string
  subtitle: string
  barClass: string
  format: (val: number) => string
}> = [
  {
    key: 'revenue_usd',
    tabLabel: 'Ingresos',
    subtitle: 'Ingresos en USD por mes',
    barClass: 'bg-primary',
    format: (v) => (v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`),
  },
  {
    key: 'new_users',
    tabLabel: 'Usuarios',
    subtitle: 'Nuevos registros por mes',
    barClass: 'bg-success',
    format: (v) => v.toLocaleString('es-ES'),
  },
  {
    key: 'songs_generated',
    tabLabel: 'Canciones',
    subtitle: 'Canciones generadas por mes',
    barClass: 'bg-warning',
    format: (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toLocaleString('es-ES')),
  },
]

export default function MonthlyChartCard({ series }: { series: MonthlySeriesPoint[] }) {
  const [activeKey, setActiveKey] = useState<MetricKey>('revenue_usd')
  const activeTab = TABS.find((t) => t.key === activeKey) ?? TABS[0]
  const maxVal = Math.max(...series.map((row) => row[activeKey]), 1)

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white">Evolución mensual</h2>
          <p className="mt-0.5 text-xs text-muted">
            {activeTab.subtitle} — {new Date().getFullYear()}
          </p>
        </div>

        <div className="flex gap-1.5">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveKey(t.key)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeKey === t.key
                  ? 'bg-primary text-black'
                  : 'bg-card-hover text-muted hover:text-white'
              }`}
            >
              {t.tabLabel}
            </button>
          ))}
        </div>
      </div>

      <div className="flex h-44 items-end gap-2">
        {series.map((row) => {
          const value = row[activeKey]
          const pct = value > 0 ? Math.max((value / maxVal) * 100, 6) : 3
          return (
            <div key={row.month} className="flex h-full flex-1 flex-col items-center gap-1">
              <span className="h-3.5 text-[10px] tabular-nums text-muted">
                {value > 0 ? activeTab.format(value) : ''}
              </span>

              <div className="flex w-full flex-1 items-end">
                <div
                  title={`${row.label}: ${activeTab.format(value)}`}
                  className={`w-full rounded-t-md transition-all duration-500 ${
                    value > 0 ? activeTab.barClass : 'bg-card-hover'
                  }`}
                  style={{ height: `${pct}%` }}
                />
              </div>

              <span className="text-[10px] text-muted">{row.label}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
