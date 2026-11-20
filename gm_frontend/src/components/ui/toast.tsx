import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

import { cn } from '../../lib/cn'
import { useToastStore, type ToastType } from '../../store/toast.store'

const TYPE_STYLES: Record<ToastType, { border: string; iconColor: string }> = {
  success: { border: 'border-success/40', iconColor: 'text-success' },
  error: { border: 'border-error-border', iconColor: 'text-error' },
  warning: { border: 'border-warning/40', iconColor: 'text-warning' },
  info: { border: 'border-info/40', iconColor: 'text-info' },
}

function ToastIcon({ type }: { type: ToastType }) {
  const cls = cn('shrink-0 mt-0.5', TYPE_STYLES[type].iconColor)
  if (type === 'success') {
    return <CheckCircle2 size={18} className={cls} aria-hidden="true" />
  }
  if (type === 'error') {
    return <AlertCircle size={18} className={cls} aria-hidden="true" />
  }
  if (type === 'warning') {
    return <AlertTriangle size={18} className={cls} aria-hidden="true" />
  }
  return <Info size={18} className={cls} aria-hidden="true" />
}

export function Toaster() {
  const toasts = useToastStore((state) => state.toasts)
  const dismissToast = useToastStore((state) => state.dismissToast)

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed bottom-4 right-4 z-[70] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2"
    >
      {toasts.map((item) => (
        <div
          key={item.id}
          role="status"
          className={cn(
            'pointer-events-auto flex items-start gap-3 rounded-xl border bg-card p-3.5 shadow-[var(--shadow)]',
            TYPE_STYLES[item.type].border
          )}
        >
          <ToastIcon type={item.type} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-white">{item.title}</p>
            {item.description && (
              <p className="mt-0.5 text-xs leading-relaxed text-muted">{item.description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={() => dismissToast(item.id)}
            aria-label="Cerrar notificación"
            className="rounded-md p-1 text-muted transition-colors hover:bg-card-hover hover:text-white"
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  )
}
