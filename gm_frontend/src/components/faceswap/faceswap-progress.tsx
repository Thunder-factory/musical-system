import { AlertCircle, LoaderCircle } from 'lucide-react'

import type { FaceSwapStatus } from '../../types/faceswap.types'

interface Props {
  status: FaceSwapStatus | null
  progress: number
  error: string | null
  loadingStatus: boolean
}

function stageLabel(status: FaceSwapStatus | null, progress: number): string {
  if (!status) {
    return 'Consultando estado…'
  }
  if (status === 'queued') {
    return 'En cola…'
  }
  if (progress < 10) {
    return 'Preparando video…'
  }
  return progress < 90 ? 'Cambiando caras…' : 'Finalizando…'
}

/** Progreso real del job (Modal) o su error final. */
export default function FaceSwapProgress({ status, progress, error, loadingStatus }: Props) {
  if (status === 'failed') {
    return (
      <div
        className="flex items-start gap-3 rounded-lg px-4 py-4"
        role="alert"
        style={{
          background: 'var(--color-error-soft)',
          border: '1px solid var(--color-error-border)',
        }}
      >
        <AlertCircle size={18} className="mt-0.5 shrink-0 text-error" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-error">No se pudo generar el video</p>
          {error && <p className="mt-1 break-words text-sm text-white">{error}</p>}
          <p className="mt-1 text-xs text-muted">Los créditos no se cobraron.</p>
        </div>
      </div>
    )
  }

  if (!status && !loadingStatus) {
    return error ? (
      <p className="text-sm" style={{ color: 'var(--color-error)' }}>
        {error}
      </p>
    ) : null
  }

  const safe = Math.max(0, Math.min(100, progress))
  return (
    <div className="flex flex-col gap-3 rounded-lg bg-card-hover px-4 py-5" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-sm font-semibold text-white">
          <LoaderCircle size={16} className="animate-spin text-primary" aria-hidden="true" />
          {stageLabel(status, safe)}
        </span>
        <span className="text-sm font-bold tabular-nums text-white">{safe}%</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-surface"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={safe}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${safe}%`, background: 'var(--gradient-primary)' }}
        />
      </div>
      <p className="text-xs text-muted">
        Suele tardar entre 2 y 6 minutos. Puedes salir de la página, te avisaremos.
      </p>
    </div>
  )
}
