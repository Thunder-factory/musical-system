import {
  createContext,
  useContext,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from 'react'

import { cn } from '../../lib/cn'

interface FieldContextValue {
  inputId: string
  errorId?: string
  hasError: boolean
}

const FormFieldContext = createContext<FieldContextValue | null>(null)

export interface FormFieldProps {
  label: string
  htmlFor?: string
  error?: string
  hint?: string
  required?: boolean
  className?: string
  children: ReactNode
}

export function FormField({
  label,
  htmlFor,
  error,
  hint,
  required = false,
  className,
  children,
}: FormFieldProps) {
  const autoId = useId()
  const inputId = htmlFor ?? `field-${autoId}`
  const msgId = error || hint ? `${inputId}-msg` : undefined

  return (
    <FormFieldContext.Provider value={{ inputId, errorId: msgId, hasError: Boolean(error) }}>
      <div className={cn('flex flex-col gap-1.5', className)}>
        <label htmlFor={inputId} className="text-xs font-semibold text-muted">
          {label}
          {required && <span className="ml-1 text-error">*</span>}
        </label>
        {children}
        {error ? (
          <p id={msgId} className="text-xs text-error">
            {error}
          </p>
        ) : (
          hint && (
            <p id={msgId} className="text-xs text-muted">
              {hint}
            </p>
          )
        )}
      </div>
    </FormFieldContext.Provider>
  )
}

const CONTROL_BASE =
  'w-full rounded-lg border bg-card-hover px-3.5 py-2.5 text-sm text-white placeholder:text-[var(--text-placeholder)] transition-colors focus:outline-none disabled:cursor-not-allowed disabled:opacity-50'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
}

export function Input({ id, error, className, ...rest }: InputProps) {
  const field = useContext(FormFieldContext)
  const hasError = error ?? field?.hasError ?? false

  return (
    <input
      id={id ?? field?.inputId}
      aria-invalid={hasError || undefined}
      aria-describedby={field?.errorId}
      className={cn(
        CONTROL_BASE,
        hasError ? 'border-error focus:border-error' : 'border-border-strong focus:border-primary',
        className
      )}
      {...rest}
    />
  )
}

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean
}

export function Textarea({ id, error, className, ...rest }: TextareaProps) {
  const field = useContext(FormFieldContext)
  const hasError = error ?? field?.hasError ?? false

  return (
    <textarea
      id={id ?? field?.inputId}
      aria-invalid={hasError || undefined}
      aria-describedby={field?.errorId}
      className={cn(
        CONTROL_BASE,
        'min-h-[96px] resize-y',
        hasError ? 'border-error focus:border-error' : 'border-border-strong focus:border-primary',
        className
      )}
      {...rest}
    />
  )
}
