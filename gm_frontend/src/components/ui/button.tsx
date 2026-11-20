import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import { LoaderCircle } from 'lucide-react'

import { cn } from '../../lib/cn'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  costCredits?: number
  leftIcon?: ReactNode
  ref?: Ref<HTMLButtonElement>
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-primary hover:bg-primary-hover text-black font-semibold border border-transparent',
  secondary:
    'bg-card-hover hover:bg-border-strong text-white border border-border-strong font-medium',
  ghost: 'bg-transparent hover:bg-card-hover text-muted hover:text-white border border-transparent',
  danger: 'bg-error-soft hover:bg-error/20 text-error border border-error-border font-medium',
}

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-xs rounded-lg gap-1.5',
  md: 'h-10 px-4 text-sm rounded-lg gap-2',
  lg: 'h-11 px-5 text-sm rounded-xl gap-2',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  costCredits,
  leftIcon,
  disabled,
  className,
  type = 'button',
  children,
  ref,
  ...rest
}: ButtonProps) {
  const isDisabled = Boolean(disabled || loading)
  const pillClass =
    variant === 'primary' ? 'bg-black/15 text-black' : 'bg-primary-soft text-primary'

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap transition-colors',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className
      )}
      {...rest}
    >
      {loading ? (
        <LoaderCircle size={size === 'sm' ? 14 : 16} className="animate-spin shrink-0" aria-hidden="true" />
      ) : (
        leftIcon && <span className="shrink-0 inline-flex items-center">{leftIcon}</span>
      )}
      <span>{children}</span>
      {costCredits !== undefined && (
        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-[11px] font-semibold leading-none',
            pillClass
          )}
        >
          · {costCredits} {costCredits === 1 ? 'crédito' : 'créditos'}
        </span>
      )}
    </button>
  )
}
