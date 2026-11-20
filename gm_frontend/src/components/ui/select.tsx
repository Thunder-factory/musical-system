import { useCallback, useId, useRef, useState, type KeyboardEvent } from 'react'
import { Check, ChevronDown } from 'lucide-react'

import { useDismissableLayer } from '../../hooks/useDismissableLayer'
import { cn } from '../../lib/cn'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps {
  label?: string
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  error?: string
  id?: string
  className?: string
}

export function Select({
  label,
  value,
  onChange,
  options,
  placeholder = 'Seleccionar...',
  disabled = false,
  error,
  id,
  className,
}: SelectProps) {
  const autoId = useId()
  const buttonId = id ?? `select-${autoId}`
  const labelId = `${buttonId}-label`
  const containerRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const selected = options.find((opt) => opt.value === value)
  const close = useCallback(() => setOpen(false), [])
  useDismissableLayer(containerRef, open, close)

  function move(step: 1 | -1) {
    for (let i = 1; i <= options.length; i += 1) {
      const idx = (activeIndex + step * i + options.length) % options.length
      if (!options[idx]?.disabled) {
        setActiveIndex(idx)
        return
      }
    }
  }

  function toggleOpen() {
    if (disabled) {
      return
    }
    if (!open) {
      const idx = options.findIndex((o) => o.value === value && !o.disabled)
      setActiveIndex(idx >= 0 ? idx : options.findIndex((o) => !o.disabled))
    }
    setOpen((prev) => !prev)
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (disabled) {
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) {
        toggleOpen()
      } else {
        move(event.key === 'ArrowDown' ? 1 : -1)
      }
    } else if ((event.key === 'Enter' || event.key === ' ') && !open) {
      event.preventDefault()
      toggleOpen()
    } else if ((event.key === 'Enter' || event.key === ' ') && open) {
      event.preventDefault()
      const current = options[activeIndex]
      if (current && !current.disabled) {
        onChange(current.value)
        setOpen(false)
      }
    }
  }

  return (
    <div ref={containerRef} className={cn('relative flex flex-col gap-1.5', className)}>
      {label && <label id={labelId} htmlFor={buttonId} className="text-xs font-semibold text-muted">{label}</label>}
      <button
        id={buttonId}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-labelledby={label ? `${labelId} ${buttonId}` : undefined}
        onClick={toggleOpen}
        onKeyDown={onKeyDown}
        className={cn(
          'flex h-10 w-full items-center justify-between gap-2 rounded-lg border bg-card-hover px-3.5 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50',
          error ? 'border-error' : open ? 'border-primary' : 'border-border-strong'
        )}
      >
        <span className={cn('truncate', selected ? 'text-white' : 'text-[var(--text-placeholder)]')}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronDown size={16} aria-hidden="true" className={cn('shrink-0 text-muted transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <ul role="listbox" className="absolute left-0 right-0 top-[calc(100%+4px)] z-40 max-h-60 overflow-y-auto rounded-xl border border-border-strong bg-surface p-1 shadow-[var(--shadow)]">
          {options.map((opt, idx) => (
            <li
              key={opt.value}
              role="option"
              aria-selected={opt.value === value}
              aria-disabled={opt.disabled || undefined}
              onMouseEnter={() => !opt.disabled && setActiveIndex(idx)}
              onClick={() => !opt.disabled && (onChange(opt.value), setOpen(false))}
              className={cn(
                'flex cursor-pointer items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                opt.disabled && 'cursor-not-allowed opacity-40',
                idx === activeIndex && !opt.disabled && 'bg-card-hover',
                opt.value === value ? 'font-semibold text-primary' : 'text-white'
              )}
            >
              <span className="truncate">{opt.label}</span>
              {opt.value === value && <Check size={14} className="shrink-0 text-primary" aria-hidden="true" />}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="text-xs text-error">{error}</p>}
    </div>
  )
}
