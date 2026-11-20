import { ArrowLeft, Mic2, Music2 } from 'lucide-react'
import { useLocation, useParams } from 'react-router-dom'

import { Button } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import { GenerateAlertCard, GeneratingView } from '../components/generate-status-card'
import { useKaraokeGeneration } from '../hooks/useKaraokeGeneration'

export default function KaraokeGeneratePage() {
  const { songId } = useParams<{ songId: string }>()
  const { state } = useLocation() as {
    state?: { songTitle?: string; source?: string; thumbnailUrl?: string }
  }
  const creditBalance = useAuthStore((s) => s.user?.credit_balance ?? 0)
  const songTitle = state?.songTitle ?? 'Canción'
  const thumbnailUrl = state?.thumbnailUrl ?? null

  const { stage, activeStep, errorMessage, start, reset, cancelAndGoBack } = useKaraokeGeneration(
    songId,
    songTitle,
    state?.source
  )

  return (
    <div className="min-h-full px-6 pb-20 pt-7 text-white sm:px-8">
      <div className="mb-6 flex flex-col items-start gap-2">
        <button
          type="button"
          onClick={cancelAndGoBack}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted transition-colors hover:text-white"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          Volver al catálogo
        </button>
        <h1 className="text-3xl font-bold tracking-tight">Preparar karaoke</h1>
        <p className="text-sm text-muted">
          Genera una versión instrumental con letra sincronizada.
        </p>
      </div>

      <div className="grid max-w-5xl gap-6 md:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-2xl border border-border bg-card p-5">
          <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-card-hover">
            {thumbnailUrl ? (
              <img
                src={thumbnailUrl}
                alt={`Portada de ${songTitle}`}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted">
                <Music2 size={44} aria-hidden="true" />
              </div>
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-night via-transparent to-transparent" />
            <p className="absolute bottom-3.5 left-4 right-4 truncate text-lg font-bold text-white">
              {songTitle}
            </p>
          </div>
          <p className="mt-4 text-[11px] font-bold uppercase tracking-wider text-muted">
            Canción seleccionada
          </p>
          <p className="mt-1.5 text-sm text-muted">
            Se separará la pista instrumental y se sincronizará la letra para cantar.
          </p>
        </section>

        <section className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card">
          {stage === 'confirm' ? (
            <div className="flex flex-1 flex-col justify-between gap-7 p-7">
              <div className="space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
                  Lista para generar
                </span>
                <h2 className="text-xl font-bold text-white">Crea tu karaoke</h2>
                <p className="text-sm text-muted">
                  Separaremos la voz, prepararemos el instrumental y sincronizaremos la letra.
                </p>
              </div>

              <div className="flex items-center justify-between rounded-xl border border-border bg-surface px-4 py-3">
                <div>
                  <p className="text-xs text-muted">Costo de generación</p>
                  <p className="text-lg font-extrabold text-white">2 créditos</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted">Tus créditos</p>
                  <p className="text-base font-bold tabular-nums text-primary">{creditBalance}</p>
                </div>
              </div>

              <div className="flex flex-col gap-2.5">
                <Button
                  variant="primary"
                  size="lg"
                  costCredits={2}
                  leftIcon={<Mic2 size={15} />}
                  onClick={() => void start()}
                  className="w-full"
                >
                  Generar Karaoke
                </Button>
                <Button variant="secondary" className="w-full" onClick={cancelAndGoBack}>
                  Cancelar
                </Button>
              </div>
            </div>
          ) : stage === 'generating' ? (
            <GeneratingView activeStep={activeStep} />
          ) : (
            <GenerateAlertCard
              variant={stage}
              creditBalance={creditBalance}
              errorMessage={errorMessage}
              onBack={cancelAndGoBack}
              onRetry={reset}
            />
          )}
        </section>
      </div>
    </div>
  )
}
