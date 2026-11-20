import { MessageCircle } from 'lucide-react'
import type { Ref } from 'react'

import { Badge } from '../../../components/ui'
import { cn } from '../../../lib/cn'

interface AssistantLauncherProps {
  offsetClass: string
  /** Muestra tooltip y badge "Nuevo" (primera visita). */
  showHint: boolean
  onOpen: () => void
  buttonRef: Ref<HTMLButtonElement>
}

/** Burbuja flotante abajo a la derecha que abre el asistente. */
export default function AssistantLauncher({
  offsetClass,
  showHint,
  onOpen,
  buttonRef,
}: AssistantLauncherProps) {
  return (
    <div className={cn('fixed right-4 z-30 flex items-center gap-2', offsetClass)}>
      {showHint && (
        <span
          className="hidden rounded-lg border border-border-strong bg-card px-3 py-1.5 text-xs text-white shadow-[var(--shadow)] sm:inline"
          aria-hidden="true"
        >
          ¿Necesitas ayuda? Pregúntame
        </span>
      )}
      <button
        ref={buttonRef}
        type="button"
        onClick={onOpen}
        aria-label="Abrir Asistente MusicAI"
        aria-haspopup="dialog"
        title="Asistente MusicAI"
        className="relative flex h-14 w-14 items-center justify-center rounded-full bg-primary text-black shadow-[var(--shadow)] transition-transform hover:scale-105 hover:bg-primary-hover"
      >
        <MessageCircle size={24} aria-hidden="true" />
        {showHint && (
          <Badge variant="neutral" className="absolute -right-1 -top-1 bg-card text-primary">
            Nuevo
          </Badge>
        )}
      </button>
    </div>
  )
}
