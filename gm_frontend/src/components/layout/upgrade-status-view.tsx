import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'

import { Button } from '../ui'

interface UpgradeStatusViewProps {
  status: 'processing' | 'success' | 'error'
  errorMsg: string
  onRetry: () => void
  onClose: () => void
}

export default function UpgradeStatusView({
  status,
  errorMsg,
  onRetry,
  onClose,
}: UpgradeStatusViewProps) {
  if (status === 'processing') {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
        <LoaderCircle size={40} className="animate-spin text-primary" aria-hidden="true" />
        <p className="font-bold text-white">Procesando pago...</p>
        <p className="text-xs text-muted">No cierres esta ventana hasta finalizar.</p>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
        <CheckCircle2 size={44} className="text-success" aria-hidden="true" />
        <p className="text-lg font-bold text-white">Tu suscripción está activa</p>
        <p className="text-sm text-muted">Ya puedes usar tus nuevos créditos en MusicAI.</p>
        <Button className="mt-2" onClick={onClose}>
          Continuar
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
      <AlertCircle size={44} className="text-error" aria-hidden="true" />
      <p className="text-sm text-muted">{errorMsg}</p>
      <div className="mt-2 flex gap-2.5">
        <Button onClick={onRetry}>Intentar de nuevo</Button>
        <Button variant="secondary" onClick={onClose}>
          Cancelar
        </Button>
      </div>
    </div>
  )
}
