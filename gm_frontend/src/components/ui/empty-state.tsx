import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { Button } from './button'

export interface EmptyStateProps {
  icon: ReactNode
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  actionTo?: string
  className?: string
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  actionTo,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-border bg-card/70 px-6 py-10 text-center',
        className
      )}
    >
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary-soft text-primary">
        {icon}
      </div>
      <h3 className="text-base font-bold text-white">{title}</h3>
      <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted">{description}</p>
      {actionLabel &&
        (actionTo ? (
          <Link
            to={actionTo}
            className="mt-5 inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-black transition-colors hover:bg-primary-hover"
          >
            {actionLabel}
          </Link>
        ) : (
          onAction && (
            <Button className="mt-5" onClick={onAction}>
              {actionLabel}
            </Button>
          )
        ))}
    </div>
  )
}
