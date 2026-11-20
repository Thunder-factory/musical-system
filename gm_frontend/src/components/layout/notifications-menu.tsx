import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'

import type { Notification } from '../../api/notifications.api'
import { cn } from '../../lib/cn'
import { DropdownMenu } from '../ui'

interface NotificationsMenuProps {
  notifications: Notification[]
  unreadCount: number
  onMarkRead: (id: number) => void
  onMarkAllRead: () => void
}

function resolveNotificationRoute(type: string): string {
  const normalized = type.toLowerCase()
  if (normalized === 'song_ready' || normalized === 'song_published' || normalized.startsWith('song_')) {
    return '/library'
  }
  if (normalized === 'stem_ready' || normalized.startsWith('stem_')) {
    return '/stems'
  }
  if (normalized.startsWith('faceswap_')) {
    return '/faceswap'
  }
  if (normalized.startsWith('translation_')) {
    return '/traducciones'
  }
  if (normalized.startsWith('humming_')) {
    return '/humming'
  }
  if (normalized.startsWith('mix_')) {
    return '/mix'
  }
  if (normalized.startsWith('karaoke_')) {
    return '/karaoke'
  }
  return '/inicio'
}

export default function NotificationsMenu({
  notifications,
  unreadCount,
  onMarkRead,
  onMarkAllRead,
}: NotificationsMenuProps) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu
      open={open}
      onOpenChange={setOpen}
      align="right"
      triggerAriaLabel="Notificaciones"
      triggerClassName="relative h-9 w-9 text-muted hover:bg-card-hover hover:text-white"
      panelClassName="w-80 max-w-[calc(100vw-1rem)]"
      trigger={
        <>
          <Bell size={18} aria-hidden="true" />
          {unreadCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-black">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </>
      }
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-xs font-bold text-white">Notificaciones</span>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={onMarkAllRead}
            className="text-xs font-medium text-primary hover:underline"
          >
            Marcar todas leídas
          </button>
        )}
      </div>

      <div className="max-h-80 overflow-y-auto">
        {notifications.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-muted">No tienes notificaciones.</p>
        ) : (
          notifications.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                if (!item.is_read) {
                  onMarkRead(item.id)
                }
                setOpen(false)
                navigate(resolveNotificationRoute(item.type))
              }}
              className={cn(
                'flex w-full flex-col gap-1 border-b border-border px-4 py-3 text-left transition-colors hover:bg-card-hover',
                !item.is_read && 'bg-primary-soft'
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <span className={cn('text-xs text-white', !item.is_read && 'font-semibold')}>
                  {item.title}
                </span>
                {!item.is_read && (
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                )}
              </div>
              {item.message && <p className="text-xs text-muted">{item.message}</p>}
            </button>
          ))
        )}
      </div>
    </DropdownMenu>
  )
}
