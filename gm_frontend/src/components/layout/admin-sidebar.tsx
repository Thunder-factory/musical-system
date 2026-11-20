import { useEffect } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { ArrowLeft, LogOut, X } from 'lucide-react'

import { cn } from '../../lib/cn'
import { ADMIN_NAV } from './app-nav'

interface AdminSidebarProps {
  open: boolean
  onClose: () => void
  onLogout: () => void
}

export default function AdminSidebar({ open, onClose, onLogout }: AdminSidebarProps) {
  useEffect(() => {
    if (!open) {
      return
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [open, onClose])

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/65 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-2 left-2 z-50 flex w-64 min-h-0 flex-col transition-transform duration-200 lg:static lg:z-auto lg:w-auto lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-[calc(100%+16px)] lg:translate-x-0'
        )}
      >
        <div className="flex h-full min-h-0 flex-col rounded-lg bg-surface p-2">
          <header className="mb-2 flex items-center justify-between px-2 py-1.5">
            <Link to="/admin" onClick={onClose} className="flex items-center gap-2.5">
              <img src="/logo.png" alt="MusicAI" className="h-8 w-8 object-contain" />
              <span className="text-base font-bold tracking-tight text-white">MusicAI Admin</span>
            </Link>
            <button
              type="button"
              onClick={onClose}
              aria-label="Cerrar menú"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-card-hover hover:text-white lg:hidden"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </header>

          <div className="mx-1 border-t border-border" aria-hidden="true" />

          <nav className="flex-1 space-y-1 overflow-y-auto px-1 py-3" aria-label="Administración">
            {ADMIN_NAV.map(({ to, label, icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/admin'}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-primary text-black font-semibold'
                      : 'text-muted hover:bg-card-hover hover:text-white'
                  )
                }
              >
                {icon}
                <span className="truncate">{label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="mt-2 space-y-1 border-t border-border pt-2">
            <Link
              to="/inicio"
              onClick={onClose}
              className="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm text-muted transition-colors hover:bg-card-hover hover:text-white"
            >
              <ArrowLeft size={16} aria-hidden="true" />
              <span>Volver a MusicAI</span>
            </Link>
            <button
              type="button"
              onClick={onLogout}
              className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm text-muted transition-colors hover:bg-error-soft hover:text-error"
            >
              <LogOut size={16} aria-hidden="true" />
              <span>Cerrar sesión</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
