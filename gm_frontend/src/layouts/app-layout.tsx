import { useState, useEffect, useRef } from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth.store'
import { ENDPOINTS } from '../api/endpoints'
import client from '../api/client'
import UpgradeModal from './upgrade-modal'
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/modules/notifications.api'
import type { Notification } from '../api/modules/notifications.api'
import { enableWebPush, listenForegroundNotifications } from '../services/firebase-messaging'
import {
  AudioWaveform,
  Bell,
  BellOff,
  BellRing,
  ChevronDown,
  CreditCard,
  Home,
  Library,
  ListMusic,
  LoaderCircle,
  LogOut,
  Mic2,
  Music2,
  SlidersHorizontal,
  Sparkles,
  UserRound,
  UsersRound,
} from 'lucide-react'

const NAV_ITEMS = [
  {
    to: '/Inicio',
    label: 'Inicio',
    icon: <Home size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/create',
    label: 'Crear canción',
    icon: <Music2 size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/library',
    label: 'Biblioteca',
    icon: <Library size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/stems',
    label: 'Separar pistas',
    icon: <AudioWaveform size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/playlists',
    label: 'Playlists',
    icon: <ListMusic size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/recommendations',
    label: 'Recomendaciones',
    icon: <Sparkles size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/community',
    label: 'Comunidad',
    icon: <UsersRound size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/karaoke',
    label: 'Karaoke',
    icon: <Mic2 size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/mix',
    label: 'Mix DJ',
    icon: <SlidersHorizontal size={18} strokeWidth={2} aria-hidden="true" />,
  },
  {
    to: '/payments',
    label: 'Pagos',
    icon: <CreditCard size={18} strokeWidth={2} aria-hidden="true" />,
  },
]

interface Suscripcion {
  id: string
  plan: { id: number; slug: string; name: string }
  status: string
}

type PushStatus = 'checking' | 'default' | 'granted' | 'denied' | 'unsupported'

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout, setUser } = useAuthStore()

  const [planBadge, setPlanBadge] = useState<string | null>(null)
  const [checkingPlan, setCheckingPlan] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [notifs, setNotifs] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)
  const [showNotifs, setShowNotifs] = useState(false)
  const [enablingPush, setEnablingPush] = useState(false)
  const [pushStatus, setPushStatus] = useState<PushStatus>('checking')
  const [pushError, setPushError] = useState<string | null>(null)
  const notifRef = useRef<HTMLDivElement>(null)
  const avatarMenuRef = useRef<HTMLDivElement>(null)
  const [showAvatarMenu, setShowAvatarMenu] = useState(false)

  useEffect(() => {
    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
      setPushStatus('unsupported')
      return
    }

    setPushStatus(Notification.permission)
  }, [])

  useEffect(() => {
    if (!pushError) {
      return
    }

    const timeout = window.setTimeout(() => setPushError(null), 5000)
    return () => window.clearTimeout(timeout)
  }, [pushError])

  useEffect(() => {
    if (!user?.id) {
      setCheckingPlan(false)
      return
    }

    client
      .get(ENDPOINTS.auth.me)
      .then(({ data }) => {
        setUser(data)
      })
      .catch((err) => {
        console.error('Error al sincronizar perfil:', err)
      })

    const fetchNotifs = () =>
      getNotifications()
        .then((r) => {
          setNotifs(r.results)
          setUnread(r.unread_count)
        })
        .catch(() => {})

    fetchNotifs()
    const interval = setInterval(fetchNotifs, 30_000)

    client
      .get(ENDPOINTS.credits.subscriptions)
      .then(({ data }: { data: Suscripcion[] }) => {
        const activa = data.find((s) => s.status === 'active')
        if (activa?.plan?.slug && activa.plan.slug !== 'free') {
          setPlanBadge(activa.plan.name.toUpperCase())
        }
      })
      .catch(() => {})
      .finally(() => setCheckingPlan(false))

    return () => clearInterval(interval)
  }, [user?.id])

  useEffect(() => {
    let unsubscribe: (() => void) | undefined
    let cancelled = false

    listenForegroundNotifications((payload) => {
      if (Notification.permission === 'granted' && payload.notification) {
        new Notification(payload.notification.title || 'Musical System', {
          body: payload.notification.body || '',
          icon: '/logo.png',
        })
      }
    })
      .then((stop) => {
        if (cancelled) {
          stop()
        } else {
          unsubscribe = stop
        }
      })
      .catch((error) => {
        console.error('Error al escuchar FCM:', error)
      })

    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [])

  useEffect(() => {
    if (!showAvatarMenu) {
      return
    }

    function handleOutsideClick(event: MouseEvent) {
      if (!avatarMenuRef.current?.contains(event.target as Node)) {
        setShowAvatarMenu(false)
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setShowAvatarMenu(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [showAvatarMenu])

  async function handleEnablePush() {
    setEnablingPush(true)
    setPushError(null)

    try {
      await enableWebPush()
      setPushStatus('granted')
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'No se pudieron activar las notificaciones.'

      setPushStatus(
        'Notification' in window && Notification.permission === 'denied' ? 'denied' : 'default'
      )
      setPushError(message)
      console.error('Firebase Messaging:', error)
    } finally {
      setEnablingPush(false)
    }
  }

  function handleLogout() {
    setShowAvatarMenu(false)
    logout()
    navigate('/login', { replace: true })
  }

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n: string) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : '?'

  const currentNavItem = NAV_ITEMS.find(({ to }) => {
    const currentPath = location.pathname.toLowerCase()
    const navPath = to.toLowerCase()
    return currentPath === navPath || currentPath.startsWith(`${navPath}/`)
  })

  return (
    <div
      className="grid h-screen bg-night gap-2 p-2 box-border"
      style={{ gridTemplateColumns: '280px 1fr', gridTemplateRows: '1fr' }}
    >
      <aside className="flex min-h-0 flex-col overflow-hidden">
        <div className="flex h-full min-h-0 flex-col rounded-lg bg-surface p-1">
          <header className="shrink-0">
            <div className="mb-2 ml-1 mt-2 flex h-12 items-center gap-2 px-2">
              <img src="/logo.png" alt="MusicAI" className="h-12 w-[52px] object-contain" />
              <span className="text-xl font-bold tracking-tight text-primary">MusicAI</span>
              <Sparkles
                size={14}
                strokeWidth={2.5}
                aria-label="Inteligencia artificial"
                className="-ml-1 text-primary"
              />
            </div>
          </header>

          <div className="mx-2 border-t border-card-hover" aria-hidden="true" />

          <div className="scrollbar-hidden min-h-0 flex-1 overflow-y-auto pt-3">
            <nav className="flex flex-col gap-1" aria-label="Navegación principal">
              {NAV_ITEMS.map(({ to, label, icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/inicio'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-md px-3 py-2 transition-all duration-150 ${
                      isActive
                        ? 'bg-primary text-black font-bold text-[16px]'
                        : 'text-muted hover:bg-card-hover hover:text-white text-[15px]'
                    }`
                  }
                >
                  {icon}
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>

          {!checkingPlan && !planBadge && (
            <div className="mx-2 mb-3 mt-3 shrink-0 rounded-lg border border-primary-border bg-primary-soft p-3">
              <div className="mb-2 flex items-center gap-2">
                <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-sm text-black">
                  ✦
                </span>
                <strong className="text-sm text-white">Más posibilidades</strong>
              </div>
              <p className="mb-3 text-xs leading-relaxed text-muted">
                Obtén más créditos para crear sin límites.
              </p>
              <button
                onClick={() => setShowModal(true)}
                className="w-full rounded-md bg-primary px-3 py-2 text-xs font-bold text-black transition-opacity hover:opacity-85"
              >
                Mejorar plan
              </button>
            </div>
          )}

          <footer className="mt-3 shrink-0 border-t border-card-hover pt-3">
            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-[15px] text-muted transition-all duration-150 hover:bg-card-hover hover:text-white"
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5-5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" />
              </svg>
              Cerrar sesión
            </button>
          </footer>
        </div>
      </aside>

      <main className="bg-night rounded-lg overflow-hidden flex flex-col gap-2">
        <header className="relative bg-surface rounded-lg flex items-center justify-between gap-4 px-6 py-2 shrink-0">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
              {currentNavItem?.icon}
            </div>
            <div className="min-w-0">
              <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
                Ubicación actual
              </span>
              <h1 className="truncate text-sm font-bold text-white">
                {currentNavItem?.label ?? 'Musical System'}
              </h1>
            </div>
          </div>

          <div className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-4">
            <div className="flex self-center items-center gap-2 rounded-xl bg-card p-1">
              <div className="flex items-center gap-1.5 rounded-lg bg-card-hover px-3 py-1.5">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  style={{ color: 'var(--color-primary)' }}
                >
                  <path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z" />
                </svg>
                {checkingPlan ? (
                  <span className="text-xs" style={{ color: 'var(--text-subdued)' }}>
                    ...
                  </span>
                ) : (
                  <>
                    {planBadge && (
                      <span className="rounded-md bg-primary-soft px-2 py-0.5 text-[10px] font-bold text-primary">
                        {planBadge}
                      </span>
                    )}
                    <span className="text-sm font-bold text-white">
                      {user?.credit_balance ?? 0}
                    </span>
                    <span className="text-[11px] text-muted">créditos</span>
                  </>
                )}
              </div>
            </div>

            <div className="relative self-center">
              <button
                type="button"
                onClick={handleEnablePush}
                disabled={enablingPush || pushStatus !== 'default'}
                aria-label={
                  pushStatus === 'granted'
                    ? 'Notificaciones push activadas'
                    : pushStatus === 'denied'
                      ? 'Notificaciones push bloqueadas'
                      : 'Activar notificaciones push'
                }
                className={`flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition-colors disabled:cursor-default ${
                  pushStatus === 'granted'
                    ? 'bg-success-soft text-success'
                    : pushStatus === 'denied'
                      ? 'bg-error-soft text-error'
                      : pushStatus === 'unsupported' || pushStatus === 'checking'
                        ? 'bg-card-hover text-muted'
                        : 'bg-card-hover text-warning hover:bg-border-strong'
                }`}
                title={
                  pushStatus === 'granted'
                    ? 'Las notificaciones están activadas'
                    : pushStatus === 'denied'
                      ? 'El permiso está bloqueado en el navegador'
                      : pushStatus === 'unsupported'
                        ? 'Este navegador no admite notificaciones push'
                        : undefined
                }
              >
                {enablingPush || pushStatus === 'checking' ? (
                  <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
                ) : pushStatus === 'granted' ? (
                  <BellRing size={14} aria-hidden="true" />
                ) : pushStatus === 'denied' || pushStatus === 'unsupported' ? (
                  <BellOff size={14} aria-hidden="true" />
                ) : (
                  <Bell size={14} aria-hidden="true" />
                )}
                <span>
                  {pushStatus === 'granted'
                    ? 'Activadas'
                    : pushStatus === 'denied'
                      ? 'Bloqueadas'
                      : pushStatus === 'unsupported'
                        ? 'No disponibles'
                        : pushStatus === 'checking' || enablingPush
                          ? 'Comprobando'
                          : 'Activar'}
                </span>
              </button>
              {pushError && (
                <div
                  role="alert"
                  aria-live="polite"
                  className="absolute right-0 top-full z-50 mt-2 w-72 rounded-lg border border-error-border bg-card px-3 py-2 text-xs text-error shadow-lg"
                >
                  {pushError}
                </div>
              )}
            </div>
          </div>

          <div className="ml-auto flex shrink-0 items-center justify-end gap-4">
            {/* Notification bell */}
            <div ref={notifRef} style={{ position: 'relative' }}>
              <button
                onClick={() => setShowNotifs((v) => !v)}
                style={{
                  position: 'relative',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-subdued)',
                  display: 'flex',
                  alignItems: 'center',
                  padding: 6,
                  borderRadius: 6,
                }}
                title="Notificaciones"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" />
                </svg>
                {unread > 0 && (
                  <span
                    style={{
                      position: 'absolute',
                      top: -1,
                      right: 2,
                      width: 16,
                      height: 16,
                      borderRadius: '50%',
                      background: 'var(--color-primary)',
                      color: 'var(--text-base)',
                      fontSize: 10,
                      fontWeight: 700,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </button>

              {showNotifs && (
                <div
                  style={{
                    position: 'absolute',
                    top: '110%',
                    right: 0,
                    width: 320,
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 10,
                    boxShadow: 'var(--shadow)',
                    zIndex: 100,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '12px 16px',
                      borderBottom: '1px solid var(--border)',
                    }}
                  >
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-base)' }}>
                      Notificaciones
                    </span>
                    {unread > 0 && (
                      <button
                        onClick={() =>
                          markAllNotificationsRead()
                            .then(() => {
                              setUnread(0)
                              setNotifs((prev) => prev.map((n) => ({ ...n, is_read: true })))
                            })
                            .catch(() => {})
                        }
                        style={{
                          fontSize: 11,
                          color: 'var(--color-primary)',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                        }}
                      >
                        Marcar todas leídas
                      </button>
                    )}
                  </div>
                  <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                    {notifs.length === 0 ? (
                      <div
                        style={{
                          padding: '20px',
                          textAlign: 'center',
                          color: 'var(--text-subdued)',
                          fontSize: 13,
                        }}
                      >
                        Sin notificaciones
                      </div>
                    ) : (
                      notifs.map((n) => (
                        <div
                          key={n.id}
                          onClick={() => {
                            if (!n.is_read) {
                              markNotificationRead(n.id).catch(() => {})
                              setNotifs((prev) =>
                                prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x))
                              )
                              setUnread((prev) => Math.max(0, prev - 1))
                            }
                            setShowNotifs(false)
                          }}
                          style={{
                            padding: '12px 16px',
                            cursor: 'pointer',
                            background: n.is_read ? 'transparent' : 'var(--color-primary-soft)',
                            borderBottom: '1px solid var(--border)',
                            transition: 'background 0.15s',
                          }}
                          onMouseEnter={(e) =>
                            ((e.currentTarget as HTMLDivElement).style.background =
                              'var(--bg-card-hover)')
                          }
                          onMouseLeave={(e) =>
                            ((e.currentTarget as HTMLDivElement).style.background = n.is_read
                              ? 'transparent'
                              : 'var(--color-primary-soft)')
                          }
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'flex-start',
                              gap: 8,
                            }}
                          >
                            <p
                              style={{
                                margin: 0,
                                fontSize: 13,
                                fontWeight: n.is_read ? 400 : 600,
                                color: 'var(--text-base)',
                              }}
                            >
                              {n.title}
                            </p>
                            {!n.is_read && (
                              <span
                                style={{
                                  width: 7,
                                  height: 7,
                                  borderRadius: '50%',
                                  background: 'var(--color-primary)',
                                  flexShrink: 0,
                                  marginTop: 3,
                                }}
                              />
                            )}
                          </div>
                          {n.message && (
                            <p
                              style={{
                                margin: '2px 0 0',
                                fontSize: 12,
                                color: 'var(--text-subdued)',
                              }}
                            >
                              {n.message}
                            </p>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            <div ref={avatarMenuRef} className="relative mr-2">
              <button
                type="button"
                onClick={() => setShowAvatarMenu((value) => !value)}
                aria-expanded={showAvatarMenu}
                aria-haspopup="menu"
                className="flex items-center gap-2.5 rounded-lg p-1.5 text-left transition-colors hover:bg-card-hover"
                title="Abrir menú de usuario"
              >
                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={`Avatar de ${user.full_name}`}
                    className="h-8 w-8 shrink-0 rounded-full object-cover"
                    style={{ border: '2px solid var(--color-primary)' }}
                  />
                ) : (
                  <div
                    className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full text-xs font-bold text-white"
                    style={{ background: 'var(--gradient-primary)' }}
                  >
                    {initials}
                  </div>
                )}
                <div className="flex min-w-0 flex-col leading-tight">
                  <span className="block max-w-[180px] truncate text-sm font-medium text-white">
                    {user?.full_name ?? '—'}
                  </span>
                  <span className="block max-w-[180px] truncate text-[10px] text-muted">
                    {user?.email ?? '—'}
                  </span>
                </div>
                <ChevronDown
                  size={15}
                  aria-hidden="true"
                  className={`shrink-0 text-muted transition-transform ${showAvatarMenu ? 'rotate-180' : ''}`}
                />
              </button>

              {showAvatarMenu && (
                <div
                  role="menu"
                  className="absolute right-0 top-[calc(100%+8px)] z-50 w-64 overflow-hidden rounded-xl border border-border bg-surface shadow-lg"
                >
                  <div className="border-b border-border px-4 py-3">
                    <p className="truncate text-sm font-semibold text-white">
                      {user?.full_name ?? 'Usuario'}
                    </p>
                    <p className="mt-1 truncate text-xs text-muted">{user?.email ?? '—'}</p>
                  </div>
                  <div className="p-1.5">
                    <NavLink
                      to="/profile"
                      role="menuitem"
                      onClick={() => setShowAvatarMenu(false)}
                      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted transition-colors hover:bg-card-hover hover:text-white"
                    >
                      <UserRound size={16} aria-hidden="true" />
                      Perfil
                    </NavLink>
                    <NavLink
                      to="/payments"
                      role="menuitem"
                      onClick={() => setShowAvatarMenu(false)}
                      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted transition-colors hover:bg-card-hover hover:text-white"
                    >
                      <CreditCard size={16} aria-hidden="true" />
                      Pagos
                    </NavLink>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleLogout}
                      className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm text-muted transition-colors hover:bg-error-soft hover:text-error"
                    >
                      <LogOut size={16} aria-hidden="true" />
                      Cerrar sesión
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="bg-surface rounded-lg flex-1 overflow-y-auto">
          <Outlet />
        </div>
      </main>

      <UpgradeModal
        show={showModal}
        onClose={() => setShowModal(false)}
        onSuccess={(planName) => {
          setPlanBadge(planName)
          setShowModal(false)
        }}
      />
    </div>
  )
}
