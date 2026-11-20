const MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

export interface MonthlyChartDatum {
  name: string
  total: number
  index: number
}

interface MonthlySpendingChartProps {
  year: number
  data: MonthlyChartDatum[]
  selectedMonth: number | null
  onSelectMonth: (monthIndex: number | null) => void
}

export default function MonthlySpendingChart({
  year,
  data,
  selectedMonth,
  onSelectMonth,
}: MonthlySpendingChartProps) {
  const maxChart = Math.max(...data.map((d) => d.total), 1)

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-muted">Gastos por mes — {year}</p>
        {selectedMonth !== null && (
          <button
            type="button"
            onClick={() => onSelectMonth(null)}
            className="text-xs font-semibold text-primary hover:underline"
          >
            Ver todo el año
          </button>
        )}
      </div>

      <div className="flex h-36 items-end gap-1.5">
        {data.map((d) => {
          const pct = d.total > 0 ? Math.max((d.total / maxChart) * 100, 6) : 3
          const isActive = selectedMonth === d.index
          return (
            <button
              key={d.name}
              type="button"
              onClick={() => onSelectMonth(isActive ? null : d.index)}
              aria-pressed={isActive}
              aria-label={`Filtrar por ${MONTHS[d.index]} ${year}: $${d.total.toFixed(2)}`}
              className="group flex h-full flex-1 flex-col items-center gap-1 text-center"
            >
              <span className="h-3.5 text-[10px] tabular-nums text-muted">
                {d.total > 0 ? `$${d.total.toFixed(0)}` : ''}
              </span>

              <div className="flex w-full flex-1 items-end">
                <div
                  className={`w-full rounded-t-sm transition-all duration-300 ${
                    isActive
                      ? 'bg-primary'
                      : d.total > 0
                        ? 'bg-primary/50 group-hover:bg-primary/80'
                        : 'bg-card-hover group-hover:bg-border-strong'
                  }`}
                  style={{ height: `${pct}%` }}
                />
              </div>

              <span
                className={`text-[10px] ${
                  isActive ? 'font-bold text-primary' : 'text-muted group-hover:text-white'
                }`}
              >
                {d.name}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
