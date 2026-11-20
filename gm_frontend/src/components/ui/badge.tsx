import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'

export type BadgeVariant = 'neutral' | 'primary' | 'success' | 'warning' | 'error'

export interface BadgeProps {
  variant?: BadgeVariant
  children: ReactNode
  className?: string
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: 'bg-card-hover text-muted border-border-strong',
  primary: 'bg-primary-soft text-primary border-primary-border',
  success: 'bg-success-soft text-success border-success/30',
  warning: 'bg-warning/10 text-warning border-warning/30',
  error: 'bg-error-soft text-error border-error-border',
}

export function Badge({ variant = 'neutral', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold leading-tight',
        VARIANT_CLASSES[variant],
        className
      )}
    >
      {children}
    </span>
  )
}
