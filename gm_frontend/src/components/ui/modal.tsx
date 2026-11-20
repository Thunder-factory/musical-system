import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

import { cn } from '../../lib/cn'

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

export interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  size?: ModalSize
  preventClose?: boolean
  children: ReactNode
  footer?: ReactNode
}

const SIZE_CLASSES: Record<ModalSize, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-xl',
  xl: 'max-w-3xl',
}

export function Modal({
  open,
  onClose,
  title,
  size = 'md',
  preventClose = false,
  children,
  footer,
}: ModalProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) {
      return
    }

    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const focusTimer = window.requestAnimationFrame(() => {
      dialogRef.current?.focus()
    })

    return () => {
      window.cancelAnimationFrame(focusTimer)
      document.body.style.overflow = previousOverflow
      previousFocusRef.current?.focus()
    }
  }, [open])

  useEffect(() => {
    if (!open) {
      return
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !preventClose) {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, preventClose, onClose])

  if (!open || typeof document === 'undefined') {
    return null
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--overlay)] p-3 sm:p-4"
      onClick={() => {
        if (!preventClose) {
          onClose()
        }
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        className={cn(
          'flex max-h-[92vh] w-full flex-col overflow-hidden rounded-2xl border border-border-strong bg-card shadow-[var(--shadow)] focus:outline-none',
          SIZE_CLASSES[size]
        )}
      >
        <header className="flex items-center justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
          <h2 id={titleId} className="text-lg font-bold text-white">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={preventClose}
            aria-label="Cerrar"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-card-hover hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>

        {footer && (
          <footer className="flex items-center justify-end gap-2.5 border-t border-border px-5 py-4 sm:px-6">
            {footer}
          </footer>
        )}
      </div>
    </div>,
    document.body
  )
}
