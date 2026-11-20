import { useEffect, useRef } from 'react'

import { useAuthStore } from '../../../store/auth.store'
import { useAssistantFirstVisit } from '../hooks/useAssistantFirstVisit'
import { useAssistantOffset } from '../hooks/useAssistantOffset'
import { useAssistantStore } from '../store/assistant.store'
import AssistantLauncher from './assistant-launcher'
import AssistantPanel from './assistant-panel'

/**
 * Punto de montaje del asistente (solo en AppLayout de cliente, dentro de GlobalAudioProvider).
 * Muestra el lanzador o el panel y devuelve el foco al lanzador al cerrar.
 */
export default function AssistantWidget() {
  const userId = useAuthStore((s) => s.user?.id)
  const open = useAssistantStore((s) => s.open)
  const setOpen = useAssistantStore((s) => s.setOpen)
  const offsetClass = useAssistantOffset()
  const { showHint, dismissHint } = useAssistantFirstVisit(userId)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const wasOpen = useRef(open)

  useEffect(() => {
    if (wasOpen.current && !open) {
      launcherRef.current?.focus()
    }
    wasOpen.current = open
  }, [open])

  if (!userId) {
    return null
  }

  return open ? (
    <AssistantPanel offsetClass={offsetClass} />
  ) : (
    <AssistantLauncher
      offsetClass={offsetClass}
      showHint={showHint}
      buttonRef={launcherRef}
      onOpen={() => {
        dismissHint()
        setOpen(true)
      }}
    />
  )
}
