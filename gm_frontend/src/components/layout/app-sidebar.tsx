import { useEffect } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { Sparkles, X } from 'lucide-react'

import { cn } from '../../lib/cn'
import { Badge, Button } from '../ui'
import { APP_NAV_GROUPS } from './app-nav'

interface AppSidebarProps {
  open: boolean
  onClose: () => void
  planBadge: string | null
  checkingPlan: boolean
  onOpenUpgrade: () => void
}

export default function AppSidebar({
  open,
  onClose,
  planBadge,
  checkingPlan,
  onOpenUpgrade,
}: AppSidebarProps) {
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
          <header className="mb-2 flex shrink-0 items-center justify-between px-2 py-1.5">
            <Link to="/inicio" onClick={onClose} className="flex items-center gap-2.5">
              <img src="/logo.png" alt="MusicAI" className="h-9 w-9 object-contain" />
              <span className="text-lg font-bold tracking-tight text-white">MusicAI</span>
              <Sparkles size={14} className="text-primary" aria-hidden="true" />
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

          <nav className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-1 py-2" aria-label="Navegación principal">
            {APP_NAV_GROUPS.map((group) => (
              <div key={group.title}>
                <p className="mb-1 px-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted/75">
                  {group.title}
                </p>
                <div className="flex flex-col gap-0.5">
                  {group.items.map(({ to, label, icon }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={to === '/inicio'}
                      onClick={onClose}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-3 rounded-lg px-2.5 py-1.5 text-sm transition-colors',
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
                </div>
              </div>
            ))}
          </nav>

          <div className="mt-1.5 shrink-0 rounded-xl bg-primary-soft p-2.5">
            {planBadge ? (
              <>
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-white">Tu suscripción</span>
                  <Badge variant="primary">{planBadge}</Badge>
                </div>
                <Button variant="secondary" size="sm" className="w-full" onClick={onOpenUpgrade}>
                  Cambiar o recargar
                </Button>
              </>
            ) : (
              <>
                <p className="text-xs font-semibold text-white">Más posibilidades</p>
                <p className="mb-2 mt-0.5 text-xs leading-snug text-muted">
                  Obtén créditos extra para crear.
                </p>
                <Button
                  size="sm"
                  className="w-full"
                  loading={checkingPlan}
                  onClick={onOpenUpgrade}
                >
                  Mejorar plan
                </Button>
              </>
            )}
          </div>
        </div>
      </aside>
    </>
  )
}
