import { AudioLines } from 'lucide-react'

import { Badge, EmptyState, type BadgeVariant } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { HummingJob } from '../api/humming.api'
import { STATUS_LABELS, styleLabel } from '../lib/humming-constants'

interface HummingHistoryProps {
  jobs: HummingJob[]
  activeJobId: string | null
  onSelect: (id: string) => void
}

function statusVariant(status: string): BadgeVariant {
  if (status === 'completed') {
    return 'success'
  }
  if (status === 'failed') {
    return 'error'
  }
  return 'warning'
}

export default function HummingHistory({ jobs, activeJobId, onSelect }: HummingHistoryProps) {
  return (
    <section className="flex min-w-0 flex-col gap-3" aria-labelledby="humming-history-title">
      <h2 id="humming-history-title" className="text-sm font-semibold text-white">
        Tus tarareos
      </h2>

      {jobs.length === 0 ? (
        <EmptyState
          icon={<AudioLines size={20} aria-hidden="true" />}
          title="Sin tarareos todavía"
          description="Graba una melodía arriba para generar versiones musicales."
          className="py-6"
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {jobs.map((item) => {
            const active = item.id === activeJobId
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-current={active ? 'true' : undefined}
                  className={cn(
                    'flex w-full items-center justify-between gap-3 rounded-xl border bg-card-hover px-4 py-3 text-left transition-colors',
                    active ? 'border-primary' : 'border-transparent hover:border-border-strong'
                  )}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-white">
                      {item.title ||
                        (item.metadata.estilo ? styleLabel(item.metadata.estilo) : 'Tarareo')}
                    </p>
                    <p className="text-xs text-muted">
                      {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge variant={statusVariant(item.status)}>
                    {STATUS_LABELS[item.status] ?? item.status}
                  </Badge>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
