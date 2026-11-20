import { Link, useLocation } from 'react-router-dom'
import { ChevronDown, Coins, CreditCard, LogOut, Menu, UserRound } from 'lucide-react'

import type { Notification } from '../../api/notifications.api'
import type { AuthUser } from '../../store/auth.store'
import { Badge, DropdownMenu, type DropdownMenuItem } from '../ui'
import { getAppRouteMeta } from './app-nav'
import { ActiveJobsPill, PushToggleButton, type PushStatus } from './header-controls'
import NotificationsMenu from './notifications-menu'
import { UserAvatar } from './user-avatar'

interface AppHeaderProps {
  user: AuthUser | null
  planBadge: string | null
  checkingPlan: boolean
  pushStatus: PushStatus
  enablingPush: boolean
  onEnablePush: () => void
  notifications: Notification[]
  unreadCount: number
  onMarkRead: (id: number) => void
  onMarkAllRead: () => void
  onOpenMenu: () => void
  onLogout: () => void
}

export default function AppHeader({
  user,
  planBadge,
  checkingPlan,
  pushStatus,
  enablingPush,
  onEnablePush,
  notifications,
  unreadCount,
  onMarkRead,
  onMarkAllRead,
  onOpenMenu,
  onLogout,
}: AppHeaderProps) {
  const location = useLocation()
  const routeMeta = getAppRouteMeta(location.pathname)

  const accountItems: DropdownMenuItem[] = [
    { label: 'Mi perfil', to: '/profile', icon: <UserRound size={15} aria-hidden="true" /> },
    { label: 'Pagos y plan', to: '/payments', icon: <CreditCard size={15} aria-hidden="true" /> },
    {
      label: 'Cerrar sesión',
      onClick: onLogout,
      variant: 'danger',
      dividerBefore: true,
      icon: <LogOut size={15} aria-hidden="true" />,
    },
  ]

  return (
    <header className="flex shrink-0 items-center justify-between gap-3 rounded-lg bg-surface px-3 py-2 sm:px-5">
      <div className="flex min-w-0 items-center gap-2.5">
        <button
          type="button"
          onClick={onOpenMenu}
          aria-label="Abrir menú"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-card-hover hover:text-white lg:hidden"
        >
          <Menu size={20} aria-hidden="true" />
        </button>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
          {routeMeta.icon}
        </span>
        <h1 className="truncate text-sm font-bold text-white sm:text-base">{routeMeta.label}</h1>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <ActiveJobsPill />

        <Link
          to="/payments"
          title="Ver pagos y créditos"
          className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs transition-colors hover:border-border-strong hover:bg-card-hover sm:px-3"
        >
          <Coins size={15} className="shrink-0 text-primary" aria-hidden="true" />
          {checkingPlan ? (
            <span className="text-muted">...</span>
          ) : (
            <>
              {planBadge && (
                <Badge variant="primary" className="hidden md:inline-flex">
                  {planBadge}
                </Badge>
              )}
              <span className="font-bold text-white">{user?.credit_balance ?? 0}</span>
              <span className="hidden text-muted sm:inline">créditos</span>
            </>
          )}
        </Link>

        <PushToggleButton status={pushStatus} enabling={enablingPush} onEnable={onEnablePush} />

        <NotificationsMenu
          notifications={notifications}
          unreadCount={unreadCount}
          onMarkRead={onMarkRead}
          onMarkAllRead={onMarkAllRead}
        />

        <DropdownMenu
          align="right"
          triggerAriaLabel="Menú de cuenta"
          triggerClassName="gap-2 p-1 hover:bg-card-hover"
          items={accountItems}
          trigger={
            <>
              <UserAvatar user={user} />
              <span className="hidden max-w-[140px] truncate text-sm font-medium text-white md:block">
                {user?.full_name ?? 'Cuenta'}
              </span>
              <ChevronDown size={14} className="hidden text-muted md:block" aria-hidden="true" />
            </>
          }
        />
      </div>
    </header>
  )
}
