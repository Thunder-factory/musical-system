import { AudioWaveform } from 'lucide-react'

import { Badge, EmptyState, type BadgeVariant } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { StemJob } from '../api/stems.api'

const STATUS_META: Record<string, { label: string; variant: BadgeVariant }> = {
  queued: { label: 'En cola', variant: 'warning' },
  processing: { label: 'Procesando', variant: 'warning' },
  completed: { label: 'Completado', variant: 'success' },
  failed: { label: 'Error', variant: 'error' },
}

interface StemHistoryProps {
  history: StemJob[]
  activeJobId: string | null
  onSelect: (jobId: string) => void
}

export default function StemHistory({ history, activeJobId, onSelect }: StemHistoryProps) {
  return (
    <section className="flex min-w-0 flex-col gap-3">
      <h2 className="text-sm font-semibold text-white">Historial de separaciones</h2>
      {history.length === 0 ? (
        <EmptyState
          icon={<AudioWaveform size={20} aria-hidden="true" />}
          title="Sin separaciones"
          description="Selecciona una canción arriba para separar sus pistas."
          className="py-6"
        />
      ) : (
        <div className="flex max-h-[420px] flex-col gap-2.5 overflow-y-auto">
          {history.map((job) => {
            const meta = STATUS_META[job.status] ?? {
              label: job.status,
              variant: 'neutral' as const,
            }
            return (
              <button
                key={job.id}
                type="button"
                onClick={() => onSelect(job.id)}
                className={cn(
                  'flex w-full items-center justify-between gap-3 rounded-xl border bg-card-hover px-4 py-3 text-left transition-colors',
                  job.id === activeJobId
                    ? 'border-primary'
                    : 'border-transparent hover:border-border-strong'
                )}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">{job.source_filename}</p>
                  <p className="text-xs text-muted">{new Date(job.created_at).toLocaleString()}</p>
                </div>
                <Badge variant={meta.variant}>
                  {meta.label}
                  {['queued', 'processing'].includes(job.status) ? ` · ${job.progress_pct}%` : ''}
                </Badge>
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
