import { useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import client from '../../api/client'
import { ENDPOINTS } from '../../api/endpoints'
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from '../../api/notifications.api'
import { isPushConfigured } from '../../lib/env'
import { enableWebPush, getPushDeviceId, listenForegroundNotifications } from '../../services/firebase-messaging'
import { useAuthStore } from '../../store/auth.store'
import { toast } from '../../store/toast.store'
import GlobalAudioPlayer from '../player/global-audio-player'
import GlobalAudioProvider from '../player/global-audio-provider'
import AppHeader from './app-header'
import AppSidebar from './app-sidebar'
import type { PushStatus } from './header-controls'
import UpgradeModal from './upgrade-modal'

interface Suscripcion {
  id: string
  plan: { id: number; slug: string; name: string }
  status: string
}

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout, setUser } = useAuthStore()

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [planBadge, setPlanBadge] = useState<string | null>(null)
  const [planSlug, setPlanSlug] = useState<string | null>(null)
  const [checkingPlan, setCheckingPlan] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [notifs, setNotifs] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)
  const [enablingPush, setEnablingPush] = useState(false)
  const [pushStatus, setPushStatus] = useState<PushStatus>('checking')

  useEffect(() => setMobileMenuOpen(false), [location.pathname])

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
      if (user?.id) {
        void getNotifications()
          .then((res) => {
            setNotifs(res.results)
            setUnread(res.unread_count)
          })
          .catch(() => {})
      }
    })
      .then((stop) => (cancelled ? stop() : (unsubscribe = stop)))
      .catch(() => {})
    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [user?.id])

  useEffect(() => {
    if (!user?.id) {
      setCheckingPlan(false)
      return
    }
    client.get(ENDPOINTS.auth.me).then(({ data }) => setUser(data)).catch(() => {})

    const fetchNotifs = () =>
      getNotifications()
        .then((res) => {
          setNotifs(res.results)
          setUnread(res.unread_count)
        })
        .catch(() => {})

    fetchNotifs()
    const interval = window.setInterval(fetchNotifs, 30_000)

    client
      .get<Suscripcion[]>(ENDPOINTS.credits.subscriptions)
      .then(({ data }) => {
        const activa = data.find((s) => s.status === 'active')
        if (activa?.plan?.slug && activa.plan.slug !== 'free') {
          setPlanBadge(activa.plan.name.toUpperCase())
          setPlanSlug(activa.plan.slug)
        }
      })
      .catch(() => {})
      .finally(() => setCheckingPlan(false))

    return () => window.clearInterval(interval)
  }, [user?.id, setUser])

  async function handleEnablePush() {
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

  async function handleMarkRead(id: number) {
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

  async function handleLogout() {
    const { refreshToken } = useAuthStore.getState()
    try {
      await client.post(ENDPOINTS.auth.logout, {
        refresh: refreshToken,
        device_id: getPushDeviceId(),
      })
    } catch {
      // La sesión local siempre debe cerrarse aunque el endpoint no responda.
    } finally {
      logout()
      navigate('/login', { replace: true })
    }
  }

  function handleMarkAllRead() {
    markAllNotificationsRead()
      .then(() => {
        setUnread(0)
        setNotifs((prev) => prev.map((n) => ({ ...n, is_read: true })))
      })
      .catch(() => {})
  }

  return (
    <div className="grid min-h-screen grid-cols-1 gap-2 bg-night p-2 box-border lg:h-screen lg:grid-cols-[256px_1fr] lg:overflow-hidden">
      <AppSidebar
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        planBadge={planBadge}
        checkingPlan={checkingPlan}
        onOpenUpgrade={() => setShowModal(true)}
      />
      <main className="flex min-h-0 min-w-0 flex-col gap-2">
        <AppHeader
          user={user}
          planBadge={planBadge}
          checkingPlan={checkingPlan}
          pushStatus={pushStatus}
          enablingPush={enablingPush}
          onEnablePush={handleEnablePush}
          notifications={notifs}
          unreadCount={unread}
          onMarkRead={handleMarkRead}
          onMarkAllRead={handleMarkAllRead}
          onOpenMenu={() => setMobileMenuOpen(true)}
          onLogout={() => void handleLogout()}
        />
        <div className="flex-1 min-h-0 overflow-y-auto rounded-lg bg-surface">
          <GlobalAudioProvider>
            <Outlet />
            <GlobalAudioPlayer />
          </GlobalAudioProvider>
        </div>
      </main>
      <UpgradeModal
        show={showModal}
        currentPlanSlug={planSlug}
        onClose={() => setShowModal(false)}
        onSuccess={(planName) => setPlanBadge(planName)}
      />
    </div>
  )
}
