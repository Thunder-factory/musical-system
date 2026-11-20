import { useCallback, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { useDismissableLayer } from '../../hooks/useDismissableLayer'
import { cn } from '../../lib/cn'

export interface DropdownMenuItem {
  id?: string
  label: string
  icon?: ReactNode
  onClick?: () => void
  to?: string
  variant?: 'default' | 'danger'
  disabled?: boolean
  dividerBefore?: boolean
}

export interface DropdownMenuProps {
  trigger: ReactNode
  items?: DropdownMenuItem[]
  align?: 'right' | 'left'
  children?: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
  triggerClassName?: string
  panelClassName?: string
  triggerAriaLabel?: string
}

export function DropdownMenu({
  trigger,
  items,
  align = 'right',
  children,
  open: controlledOpen,
  onOpenChange,
  triggerClassName,
  panelClassName,
  triggerAriaLabel,
}: DropdownMenuProps) {
  const [internalOpen, setInternalOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const isOpen = controlledOpen ?? internalOpen

  const setOpen = useCallback(
    (next: boolean) => {
      if (controlledOpen === undefined) {
        setInternalOpen(next)
      }
      onOpenChange?.(next)
    },
    [controlledOpen, onOpenChange]
  )

  const handleClose = useCallback(() => {
    setOpen(false)
  }, [setOpen])

  useDismissableLayer(containerRef, isOpen, handleClose)

  return (
    <div ref={containerRef} className="relative inline-flex">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label={triggerAriaLabel}
        onClick={() => setOpen(!isOpen)}
        className={cn(
          'inline-flex items-center justify-center rounded-lg transition-colors',
          triggerClassName
        )}
      >
        {trigger}
      </button>

      {isOpen && (
        <div
          role={items ? 'menu' : undefined}
          className={cn(
            'absolute top-[calc(100%+8px)] z-50 min-w-[200px] overflow-hidden rounded-xl border border-border-strong bg-surface shadow-[var(--shadow)]',
            align === 'right' ? 'right-0' : 'left-0',
            panelClassName
          )}
        >
          {items ? (
            <div className="p-1.5">
              {items.map((item, idx) => {
                const itemCls = cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                  item.disabled && 'pointer-events-none opacity-40',
                  item.variant === 'danger'
                    ? 'text-muted hover:bg-error-soft hover:text-error'
                    : 'text-muted hover:bg-card-hover hover:text-white'
                )
                return (
                  <div key={item.id ?? `${item.label}-${idx}`}>
                    {item.dividerBefore && <div className="my-1 border-t border-border" />}
                    {item.to ? (
                      <Link to={item.to} role="menuitem" onClick={handleClose} className={itemCls}>
                        {item.icon && <span className="shrink-0">{item.icon}</span>}
                        <span className="truncate">{item.label}</span>
                      </Link>
                    ) : (
                      <button
                        type="button"
                        role="menuitem"
                        disabled={item.disabled}
                        onClick={() => {
                          handleClose()
                          item.onClick?.()
                        }}
                        className={itemCls}
                      >
                        {item.icon && <span className="shrink-0">{item.icon}</span>}
                        <span className="truncate">{item.label}</span>
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            children
          )}
        </div>
      )}
    </div>
  )
}
