import { ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../../../components/ui'
import { isMobileViewport } from '../lib/viewport'
import { useAssistantStore } from '../store/assistant.store'
import type { AssistantAction } from '../types/assistant.types'

interface AssistantActionsProps {
  actions: AssistantAction[]
}

/** Botones de navegación propuestos por el asistente; en móvil cierran el panel. */
export default function AssistantActions({ actions }: AssistantActionsProps) {
  const navigate = useNavigate()
  const setOpen = useAssistantStore((s) => s.setOpen)

  if (actions.length === 0) {
    return null
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {actions.map((action) => (
        <Button
          key={`${action.route}-${action.label}`}
          variant="secondary"
          size="sm"
          onClick={() => {
            navigate(action.route)
            if (isMobileViewport()) {
              setOpen(false)
            }
          }}
        >
          <span className="inline-flex items-center gap-1.5">
            {action.label}
            <ArrowRight size={13} aria-hidden="true" />
          </span>
        </Button>
      ))}
    </div>
  )
}
