import { useEffect, useRef, useState } from 'react'

import type { PushStatus } from '../components/layout/header-controls'
import { isPushConfigured } from '../lib/env'
import { enableWebPush, listenForegroundNotifications } from '../services/firebase-messaging'
import { toast } from '../store/toast.store'

/**
 * Estado del push web: registra el dispositivo si ya hay permiso, escucha los mensajes
 * en primer plano (muestra la notificación y llama a `onMessage`) y permite activarlo.
 */
export function useWebPush(userId: string | undefined, onMessage: () => void) {
  const [pushStatus, setPushStatus] = useState<PushStatus>('checking')
  const [enablingPush, setEnablingPush] = useState(false)
  const onMessageRef = useRef(onMessage)
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    if (!isPushConfigured() || !('Notification' in window) || !('serviceWorker' in navigator)) {
      setPushStatus('unsupported')
      return
    }
    if (Notification.permission === 'denied') {
      setPushStatus('denied')
    } else if (Notification.permission === 'granted') {
      void enableWebPush()
        .then(() => setPushStatus('registered'))
        .catch(() => setPushStatus('granted'))
    } else {
      setPushStatus('default')
    }

    let unsubscribe: (() => void) | undefined
    let cancelled = false
    listenForegroundNotifications((payload) => {
      if (Notification.permission === 'granted' && payload.notification) {
        new Notification(payload.notification.title || 'MusicAI', {
          body: payload.notification.body || '',
          icon: '/logo.png',
        })
      }
      onMessageRef.current()
    })
      .then((stop) => (cancelled ? stop() : (unsubscribe = stop)))
      .catch(() => {})
    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [userId])

  async function enablePush() {
    setEnablingPush(true)
    try {
      await enableWebPush()
      setPushStatus('registered')
      toast.success('Notificaciones push activadas')
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'No se pudieron activar las notificaciones.'
      setPushStatus('Notification' in window && Notification.permission === 'denied' ? 'denied' : 'default')
      toast.error('No se pudo activar push', msg)
    } finally {
      setEnablingPush(false)
    }
  }

  return { pushStatus, enablingPush, enablePush }
}
