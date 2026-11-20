import { Link } from 'react-router-dom'
import { Coins, Wand2 } from 'lucide-react'

import { Button } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import { FACESWAP_CREDIT_COST } from '../types/faceswap.types'

interface Props {
  canSubmit: boolean
  submitting: boolean
  processing: boolean
  noCredits: boolean
  missing: string | null
  error: string | null
  onSubmit: () => void
}

export default function FaceSwapSubmitBar({
  canSubmit,
  submitting,
  processing,
  noCredits,
  missing,
  error,
  onSubmit,
}: Props) {
  const balance = useAuthStore((s) => s.user?.credit_balance ?? 0)
  const busy = submitting || processing

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <Coins size={16} className="text-primary" aria-hidden="true" />
          <span className="font-semibold text-white">Tu saldo: {balance} créditos</span>
        </div>
        <Button
          disabled={!canSubmit || busy || noCredits}
          loading={busy}
          costCredits={FACESWAP_CREDIT_COST}
          onClick={onSubmit}
          leftIcon={<Wand2 size={16} aria-hidden="true" />}
        >
          {submitting ? 'Subiendo…' : processing ? 'Procesando…' : 'Generar video'}
        </Button>
      </div>

      {!busy && !noCredits && missing && <p className="text-xs text-muted">{missing}</p>}

      {noCredits && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary-border bg-primary-soft px-4 py-3 text-sm">
          <p className="text-white">No tienes créditos suficientes.</p>
          <Link to="/payments" className="font-semibold text-primary underline">
            Recargar créditos
          </Link>
        </div>
      )}

      {error && !noCredits && (
        <p className="text-sm text-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
