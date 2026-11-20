import { Sparkles, X } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { cn } from '../../../lib/cn'
import { useAssistantStore } from '../store/assistant.store'
import AssistantInput from './assistant-input'
import AssistantMessageList from './assistant-message-list'
import AssistantSuggestions from './assistant-suggestions'

interface AssistantPanelProps {
  /** Clase `bottom-*` para no tapar barras inferiores. */
  offsetClass: string
}

/** Ventana del chat: casi pantalla completa en móvil, 380×560 en escritorio. */
export default function AssistantPanel({ offsetClass }: AssistantPanelProps) {
  const setOpen = useAssistantStore((s) => s.setOpen)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [setOpen])

  return (
    <section
      role="dialog"
      aria-label="Asistente MusicAI"
      className={cn(
        'fixed inset-x-2 top-2 z-[45] flex flex-col overflow-hidden rounded-2xl border border-border-strong bg-surface shadow-[var(--shadow)]',
        'sm:inset-x-auto sm:right-4 sm:top-auto sm:h-[560px] sm:max-h-[calc(100vh-7rem)] sm:w-[380px]',
        offsetClass
      )}
    >
      <header className="flex items-center gap-3 border-b border-border bg-card px-4 py-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
          <Sparkles size={18} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold text-white">Asistente MusicAI</h2>
          <p className="truncate text-xs text-muted">Te guío por la app · no gasta créditos</p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="Cerrar asistente"
          className="flex h-8 w-8 items-center justify-center rounded-full text-muted transition-colors hover:bg-card-hover hover:text-white"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </header>
      <AssistantMessageList />
      <AssistantSuggestions />
      <AssistantInput inputRef={inputRef} />
    </section>
  )
}
