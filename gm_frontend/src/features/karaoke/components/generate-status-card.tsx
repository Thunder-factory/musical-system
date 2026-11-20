import { AlertCircle, Check, Clock, Coins, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '../../../components/ui'
import { KARAOKE_STEPS } from '../hooks/useKaraokeGeneration'

export function GeneratingView({ activeStep }: { activeStep: number }) {
  return (
    <div className="flex min-h-[340px] flex-col justify-center gap-5 p-7">
      <div className="text-center">
        <p className="text-[11px] font-bold uppercase tracking-wider text-primary">
          Procesando canción
        </p>
        <h2 className="mt-1.5 text-lg font-bold text-white">Generando tu karaoke...</h2>
        <p className="mt-1 text-xs text-muted">
          Esto puede tardar unos minutos según la duración de la canción.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {KARAOKE_STEPS.map((label, i) => {
          const isDone = i < activeStep
          const isActive = i === activeStep
          return (
            <div
              key={label}
              className={`flex items-center gap-3 text-sm transition-colors ${
                isDone ? 'text-primary' : isActive ? 'font-semibold text-white' : 'text-muted'
              }`}
            >
              <div
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
                  isDone || isActive ? 'border-primary bg-primary-soft' : 'border-border-strong'
                }`}
              >
                {isDone ? (
                  <Check size={12} aria-hidden="true" />
                ) : isActive ? (
                  <LoaderCircle size={12} className="animate-spin text-primary" aria-hidden="true" />
                ) : null}
              </div>
              <span>{label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function GenerateAlertCard({
  variant,
  creditBalance,
  errorMessage,
  onBack,
  onRetry,
}: {
  variant: 'no_credits' | 'timeout' | 'error'
  creditBalance: number
  errorMessage: string | null
  onBack: () => void
  onRetry: () => void
}) {
  return (
    <div className="flex min-h-[340px] flex-col items-center justify-center gap-3.5 p-7 text-center">
      <div
        className={`flex h-12 w-12 items-center justify-center rounded-full ${
          variant === 'error' ? 'bg-error-soft text-error' : 'bg-primary-soft text-warning'
        }`}
      >
        {variant === 'no_credits' ? (
          <Coins size={22} aria-hidden="true" />
        ) : variant === 'timeout' ? (
          <Clock size={22} aria-hidden="true" />
        ) : (
          <AlertCircle size={22} aria-hidden="true" />
        )}
      </div>

      <h2 className="text-base font-bold text-white">
        {variant === 'no_credits'
          ? 'Créditos insuficientes'
          : variant === 'timeout'
            ? 'La generación continúa'
            : 'Algo salió mal'}
      </h2>

      <p className="max-w-xs text-sm text-muted">
        {variant === 'no_credits' ? (
          <>
            Necesitas 2 créditos para generar un karaoke. Actualmente tienes{' '}
            <strong className="text-white">{creditBalance}</strong>.
          </>
        ) : variant === 'timeout' ? (
          'El proceso está tardando más de lo habitual. Puedes seguir navegando y revisar en “Mis Karaokes” cuando termine.'
        ) : (
          (errorMessage ?? 'No se pudo generar el karaoke. Tus créditos no fueron descontados.')
        )}
      </p>

      <div className="mt-2 flex w-full max-w-xs flex-col gap-2">
        {variant === 'no_credits' && (
          <Link
            to="/payments"
            className="inline-flex h-10 w-full items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-black transition-colors hover:bg-primary-hover"
          >
            Ver planes
          </Link>
        )}
        {variant === 'error' && (
          <Button variant="primary" className="w-full" onClick={onRetry}>
            Intentar de nuevo
          </Button>
        )}
        <Button variant={variant === 'timeout' ? 'primary' : 'secondary'} className="w-full" onClick={onBack}>
          Volver al catálogo
        </Button>
      </div>
    </div>
  )
}
