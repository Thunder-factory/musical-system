import { ArrowUp, ScanFace } from 'lucide-react'

import { BTN_OUTLINE } from './faceswap-ui'

interface Props {
  onStart?: () => void
}

/** Estado vacío del historial con acción para empezar. */
export default function FaceSwapEmptyState({ onStart }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg bg-card px-6 py-10 text-center">
      <span
        className="flex h-14 w-14 items-center justify-center rounded-full"
        style={{ background: 'var(--color-primary-subtle)' }}
      >
        <ScanFace size={28} className="text-primary" aria-hidden="true" />
      </span>
      <div>
        <p className="text-base font-bold text-white">Aún no has creado videos</p>
        <p className="mt-1 text-sm text-muted">
          Sube tu foto, elige una plantilla y genera tu primer video.
        </p>
      </div>
      {onStart && (
        <button type="button" className={BTN_OUTLINE} onClick={onStart}>
          <ArrowUp size={14} aria-hidden="true" />
          Empezar por tu foto
        </button>
      )}
    </div>
  )
}
