import { useLocation } from 'react-router-dom'

import { getSuggestions } from '../lib/suggestions'
import { useAssistantStore } from '../store/assistant.store'

/** Chips de preguntas sugeridas según la página actual. */
export default function AssistantSuggestions() {
  const { pathname } = useLocation()
  const send = useAssistantStore((s) => s.send)
  const typing = useAssistantStore((s) => s.typing)

  return (
    <div
      className="flex gap-2 overflow-x-auto px-3 pb-2 pt-1 [scrollbar-width:none]"
      role="group"
      aria-label="Preguntas sugeridas"
    >
      {getSuggestions(pathname).map((question) => (
        <button
          key={question}
          type="button"
          disabled={typing}
          onClick={() => void send(question, pathname)}
          className="shrink-0 rounded-full border border-primary-border bg-primary-soft px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {question}
        </button>
      ))}
    </div>
  )
}
