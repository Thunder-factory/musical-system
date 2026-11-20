import { useCallback, useEffect, useState } from 'react'

import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from '../api/notifications.api'
import { toast } from '../store/toast.store'

/** Notificaciones del usuario: carga inicial, sondeo cada 30 s y marcado como leídas. */
export function useAppNotifications(userId: string | undefined) {
  const [notifs, setNotifs] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)

  const refresh = useCallback(() => {
    if (!userId) {
      return
    }
    getNotifications()
      .then((res) => {
        setNotifs(res.results)
        setUnread(res.unread_count)
      })
      .catch(() => {})
  }, [userId])

  useEffect(() => {
    if (!userId) {
      return
    }
    refresh()
    const interval = window.setInterval(refresh, 30_000)
    return () => window.clearInterval(interval)
  }, [userId, refresh])

  async function markRead(id: number) {
    const notification = notifs.find((item) => item.id === id)
    if (!notification || notification.is_read) {
      return
    }
    try {
      await markNotificationRead(id)
      setNotifs((prev) => prev.map((x) => (x.id === id ? { ...x, is_read: true } : x)))
      setUnread((prev) => Math.max(0, prev - 1))
    } catch {
      toast.error('No se pudo marcar la notificación como leída.')
    }
  }

  function markAllRead() {
    markAllNotificationsRead()
      .then(() => {
        setUnread(0)
        setNotifs((prev) => prev.map((n) => ({ ...n, is_read: true })))
      })
      .catch(() => {})
  }

  return { notifs, unread, refresh, markRead, markAllRead }
}
