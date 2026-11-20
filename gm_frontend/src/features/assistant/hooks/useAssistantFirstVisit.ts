import { useEffect, useRef, useState } from 'react'

import { hasSeenAssistant, markAssistantSeen } from '../lib/storage'
import { useAssistantStore } from '../store/assistant.store'

/**
 * Abre el asistente automáticamente la primera vez que el usuario entra y
 * reinicia el chat al cambiar de usuario. Devuelve si mostrar la pista del lanzador.
 */
export function useAssistantFirstVisit(userId: string | undefined) {
  const [showHint, setShowHint] = useState(false)
  // Evita procesar dos veces el mismo usuario (StrictMode ejecuta los efectos doble en dev).
  const handledUser = useRef<string | null>(null)

  useEffect(() => {
    if (handledUser.current === (userId ?? '')) {
      return
    }
    handledUser.current = userId ?? ''
    const { reset, setOpen } = useAssistantStore.getState()
    reset()
    if (!userId) {
      setShowHint(false)
      return
    }
    const firstTime = !hasSeenAssistant(userId)
    setShowHint(firstTime)
    if (firstTime) {
      markAssistantSeen(userId)
      setOpen(true)
    }
  }, [userId])

  return { showHint, dismissHint: () => setShowHint(false) }
}
