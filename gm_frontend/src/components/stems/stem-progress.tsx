interface Props {
  status: string | null
  progress: number
  error: string | null
  loadingStatus?: boolean
}

const STATUS_LABELS: Record<string, string> = {
  queued: 'En cola…',
  processing: 'Separando pistas…',
  completed: 'Completado',
  failed: 'Error',
}

export default function StemProgress({ status, progress, error, loadingStatus = false }: Props) {
  if (!status && !loadingStatus) {
    return null
  }

  const safeProgress = Math.max(0, Math.min(100, Number(progress) || 0))
  const label = status ? (STATUS_LABELS[status] ?? status) : 'Consultando estado…'
  const isFailed = status === 'failed'
  const isCompleted = status === 'completed'

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span
          className="text-sm font-medium"
          style={{
            color: isFailed
              ? 'var(--color-error)'
              : isCompleted
                ? 'var(--color-success)'
                : 'var(--text-base)',
          }}
        >
          {label}
        </span>
        <span className="text-xs text-muted">{safeProgress}%</span>
      </div>

      <div
        className="h-2 rounded-full overflow-hidden"
        style={{ background: 'var(--bg-card-hover)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${safeProgress}%`,
            background: isFailed
              ? 'var(--color-error)'
              : isCompleted
                ? 'var(--color-success)'
                : 'var(--color-primary)',
          }}
        />
      </div>

      {isFailed && error && (
        <p className="text-xs" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
    </div>
  )
}
