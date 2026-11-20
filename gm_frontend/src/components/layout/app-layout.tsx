import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import client from '../../api/client'
import { ENDPOINTS } from '../../api/endpoints'
import AssistantWidget from '../../features/assistant/components/assistant-widget'
import { useAppNotifications } from '../../hooks/useAppNotifications'
import { useLogout } from '../../hooks/useLogout'
import { useWebPush } from '../../hooks/useWebPush'
import { useAuthStore } from '../../store/auth.store'
import GlobalAudioPlayer from '../player/global-audio-player'
import GlobalAudioProvider from '../player/global-audio-provider'
import AppHeader from './app-header'
import AppSidebar from './app-sidebar'
import UpgradeModal from './upgrade-modal'

interface Suscripcion {
  id: string
  plan: { id: number; slug: string; name: string }
  status: string
}

export default function AppLayout() {
  const location = useLocation()
  const { user, setUser } = useAuthStore()
  const handleLogout = useLogout()
  const notifications = useAppNotifications(user?.id)
  const push = useWebPush(user?.id, notifications.refresh)

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [planBadge, setPlanBadge] = useState<string | null>(null)
  const [planSlug, setPlanSlug] = useState<string | null>(null)
  const [checkingPlan, setCheckingPlan] = useState(true)
  const [showModal, setShowModal] = useState(false)

  useEffect(() => setMobileMenuOpen(false), [location.pathname])

  useEffect(() => {
    if (!user?.id) {
      setCheckingPlan(false)
      return
    }
    client.get(ENDPOINTS.auth.me).then(({ data }) => setUser(data)).catch(() => {})
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
  }, [user?.id, setUser])

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
          pushStatus={push.pushStatus}
          enablingPush={push.enablingPush}
          onEnablePush={push.enablePush}
          notifications={notifications.notifs}
          unreadCount={notifications.unread}
          onMarkRead={notifications.markRead}
          onMarkAllRead={notifications.markAllRead}
          onOpenMenu={() => setMobileMenuOpen(true)}
          onLogout={() => void handleLogout()}
        />
        <div className="flex-1 min-h-0 overflow-y-auto rounded-lg bg-surface">
          <GlobalAudioProvider>
            <Outlet />
            <GlobalAudioPlayer />
            <AssistantWidget />
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
