import { useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, ChevronDown, LogOut, Menu, Shield, UserRound } from 'lucide-react'

import { useAuthStore } from '../../store/auth.store'
import { Badge, DropdownMenu, type DropdownMenuItem } from '../ui'
import { ADMIN_NAV } from './app-nav'
import AdminSidebar from './admin-sidebar'
import { UserAvatar } from './user-avatar'

export default function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => setDrawerOpen(false), [location.pathname])

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  const currentNav =
    ADMIN_NAV.find((item) =>
      item.to === '/admin'
        ? location.pathname === '/admin'
        : location.pathname.startsWith(item.to)
    ) ?? ADMIN_NAV[0]

  const accountItems: DropdownMenuItem[] = [
    { label: 'Mi perfil', to: '/admin/profile', icon: <UserRound size={15} aria-hidden="true" /> },
    { label: 'Volver a MusicAI', to: '/inicio', icon: <ArrowLeft size={15} aria-hidden="true" /> },
    {
      label: 'Cerrar sesión',
      onClick: handleLogout,
      variant: 'danger',
      dividerBefore: true,
      icon: <LogOut size={15} aria-hidden="true" />,
    },
  ]

  return (
    <div className="grid min-h-screen grid-cols-1 gap-2 bg-night p-2 box-border lg:h-screen lg:grid-cols-[248px_1fr] lg:overflow-hidden">
      <AdminSidebar
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onLogout={handleLogout}
      />

      <main className="flex min-h-0 min-w-0 flex-col gap-2">
        <header className="flex shrink-0 items-center justify-between gap-3 rounded-lg bg-surface px-3 py-2 sm:px-5">
          <div className="flex min-w-0 items-center gap-2.5">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="Abrir menú"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-card-hover hover:text-white lg:hidden"
            >
              <Menu size={20} aria-hidden="true" />
            </button>
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
              {currentNav.icon}
            </span>
            <h1 className="truncate text-sm font-bold text-white sm:text-base">
              {currentNav.label}
            </h1>
          </div>

          <div className="flex shrink-0 items-center gap-2.5">
            <Badge variant="primary" className="hidden sm:inline-flex">
              <Shield size={12} aria-hidden="true" />
              Administrador
            </Badge>

            <DropdownMenu
              align="right"
              triggerAriaLabel="Menú de administrador"
              triggerClassName="gap-2 p-1 hover:bg-card-hover"
              items={accountItems}
              trigger={
                <>
                  <UserAvatar user={user} />
                  <span className="hidden max-w-[160px] truncate text-sm font-medium text-white md:block">
                    {user?.full_name ?? 'Admin'}
                  </span>
                  <ChevronDown size={14} className="hidden text-muted md:block" aria-hidden="true" />
                </>
              }
            />
          </div>
        </header>

        <div className="flex-1 min-h-0 overflow-y-auto rounded-lg bg-surface">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
