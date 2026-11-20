import { useNavigate } from 'react-router-dom'
import { Coins, LoaderCircle, Wand2 } from 'lucide-react'

import { useAuthStore } from '../../store/auth.store'
import { FACESWAP_CREDIT_COST } from '../../types/faceswap.types'
import { BTN_OUTLINE, BTN_PRIMARY } from './faceswap-ui'

interface Props {
  canSubmit: boolean
  submitting: boolean
  processing: boolean
  noCredits: boolean
  missing: string | null
  error: string | null
  onSubmit: () => void
}

/** Paso 3: costo, saldo y el único botón primario de la vista ("Generar video"). */
export default function FaceSwapSubmitBar({
  canSubmit,
  submitting,
  processing,
  noCredits,
  missing,
  error,
  onSubmit,
}: Props) {
  const navigate = useNavigate()
  const balance = useAuthStore((s) => s.user?.credit_balance ?? 0)
  const busy = submitting || processing

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <Coins size={16} className="text-primary" aria-hidden="true" />
          <span className="font-semibold text-white">{FACESWAP_CREDIT_COST} créditos</span>
          <span className="text-muted">· tu saldo: {balance}</span>
        </div>
        <button
          type="button"
          className={BTN_PRIMARY}
          disabled={!canSubmit || busy || noCredits}
          onClick={onSubmit}
        >
          {busy ? (
            <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
          ) : (
            <Wand2 size={16} aria-hidden="true" />
          )}
          {submitting ? 'Subiendo…' : processing ? 'Procesando…' : 'Generar video'}
        </button>
      </div>

      {!busy && !noCredits && missing && <p className="text-xs text-muted">{missing}</p>}

      {noCredits && (
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg px-4 py-3"
          style={{
            background: 'var(--color-primary-soft)',
            border: '1px solid var(--color-primary-border)',
          }}
        >
          <p className="text-sm text-white">No tienes créditos suficientes.</p>
          <button type="button" className={BTN_OUTLINE} onClick={() => navigate('/payments')}>
            Recargar créditos
          </button>
        </div>
      )}

      {error && !noCredits && (
        <p className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
    </div>
  )
}
