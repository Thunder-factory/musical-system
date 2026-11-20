import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'

import { cn } from '../../../lib/cn'

interface StemProgressProps {
  status: string | null
  progress: number
  error: string | null
  loadingStatus?: boolean
}

const STATUS_LABELS: Record<string, string> = {
  queued: 'En cola…',
  processing: 'Separando pistas…',
  completed: 'Completado',
  failed: 'Error en la separación',
}

export default function StemProgress({
  status,
  progress,
  error,
  loadingStatus = false,
}: StemProgressProps) {
  if (!status && !loadingStatus) {
    return null
  }

  const safeProgress = Math.max(0, Math.min(100, Number(progress) || 0))
  const label = status ? (STATUS_LABELS[status] ?? status) : 'Consultando estado…'
  const isFailed = status === 'failed'
  const isCompleted = status === 'completed'

  return (
    <div
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4"
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-3">
        <span
          className={cn(
            'inline-flex items-center gap-2 text-sm font-semibold',
            isFailed ? 'text-error' : isCompleted ? 'text-success' : 'text-white'
          )}
        >
          {isFailed ? (
            <AlertCircle size={16} aria-hidden="true" />
          ) : isCompleted ? (
            <CheckCircle2 size={16} aria-hidden="true" />
          ) : (
            <LoaderCircle size={16} className="animate-spin text-primary" aria-hidden="true" />
          )}
          {label}
        </span>
        <span className="text-xs tabular-nums text-muted">{safeProgress}%</span>
      </div>

      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={safeProgress}
        className="h-2 overflow-hidden rounded-full bg-card-hover"
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            isFailed ? 'bg-error' : isCompleted ? 'bg-success' : 'bg-primary'
          )}
          style={{ width: `${safeProgress}%` }}
        />
      </div>

      {isFailed && error && (
        <p className="text-xs text-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
