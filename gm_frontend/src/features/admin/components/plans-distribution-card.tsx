import { Badge } from '../../../components/ui'
import type { PlanDistributionItem, RecentDashboardUser } from '../api/admin.api'

const BAR_COLORS = [
  'var(--text-subdued)',
  'var(--color-primary)',
  'var(--color-success)',
  'var(--color-info)',
]

export function PlansDistributionCard({ distribution }: { distribution: PlanDistributionItem[] }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <h2 className="text-sm font-bold text-white">Usuarios por plan</h2>
      <p className="mt-0.5 text-xs text-muted">Distribución actual de cuentas</p>

      <div className="mt-4 flex flex-col gap-3">
        {distribution.map((item, idx) => {
          const color = BAR_COLORS[idx % BAR_COLORS.length]
          return (
            <div key={item.slug}>
              <div className="mb-1 flex justify-between text-xs">
                <span className="font-semibold text-white">{item.name}</span>
                <span className="tabular-nums text-muted">
                  {item.users_count.toLocaleString('es-ES')} ({item.percentage}%)
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-card-hover">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(item.percentage, 0))}%`, background: color }}
                />
              </div>
            </div>
          )
        })}
        {distribution.length === 0 && (
          <p className="py-4 text-center text-xs text-muted">Sin datos de planes todavía.</p>
        )}
      </div>
    </section>
  )
}

export function RecentUsersCard({ users }: { users: RecentDashboardUser[] }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-4 text-sm font-bold text-white">Usuarios recientes</h2>

      {users.length === 0 ? (
        <p className="py-4 text-center text-xs text-muted">Sin usuarios registrados aún.</p>
      ) : (
        <div className="flex flex-col gap-2.5">
          {users.map((u) => {
            const initials = u.full_name
              ? u.full_name
                  .split(' ')
                  .map((n) => n[0])
                  .join('')
                  .slice(0, 2)
                  .toUpperCase()
              : '?'
            return (
              <div key={u.id} className="flex items-center gap-3 py-1">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--gradient-primary)] text-[11px] font-bold text-black">
                  {initials}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-white">
                    {u.full_name || 'Sin nombre'}
                  </p>
                  <p className="truncate text-[11px] text-muted">{u.email}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <Badge variant={u.plan_name.toLowerCase() === 'free' ? 'neutral' : 'primary'}>
                    {u.plan_name}
                  </Badge>
                  <span className="text-[10px] text-muted">
                    {new Date(u.created_at).toLocaleDateString('es-ES', {
                      day: '2-digit',
                      month: 'short',
                    })}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
