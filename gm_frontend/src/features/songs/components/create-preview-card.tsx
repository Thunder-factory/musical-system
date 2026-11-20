import { Link } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Coins, LoaderCircle, Sparkles } from 'lucide-react'

import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import {
  CREATE_MODE_META,
  DURATION_OPTIONS,
  LANGUAGE_OPTIONS,
  VOCAL_OPTIONS,
  type CreateMode,
  type SongLanguage,
  type VocalType,
} from '../lib/create-song-options'

export type GenerationStage = 'idle' | 'submitting' | 'polling' | 'ready' | 'no_credits' | 'error'

export interface ReadySongPreview {
  songId: string
  playUrl: string
  thumbnailUrl: string
}

const STAGE_LABELS: Record<GenerationStage, string> = {
  idle: '',
  submitting: 'Preparando tu canción...',
  polling: 'Creando tu canción...',
  ready: '¡Tu canción está lista!',
  no_credits: 'Sin créditos suficientes',
  error: 'No pudimos crearla',
}

interface CreatePreviewCardProps {
  title: string
  credits: number
  mode: CreateMode
  duration: number
  vocalType: VocalType
  language: SongLanguage
  selectedTagCount: number
  stage: GenerationStage
  ready: ReadySongPreview | null
  errorMsg: string | null
  onReset: () => void
}

export function CreatePreviewCard({
  title,
  credits,
  mode,
  duration,
  vocalType,
  language,
  selectedTagCount,
  stage,
  ready,
  errorMsg,
  onReset,
}: CreatePreviewCardProps) {
  const isBusy = stage === 'submitting' || stage === 'polling'
  const modeLabel = CREATE_MODE_META.find((item) => item.id === mode)?.label ?? 'Descripción'
  const durationLabel =
    DURATION_OPTIONS.find((item) => Number(item.value) === duration)?.label ?? `${duration} s`
  const vocalLabel = VOCAL_OPTIONS.find((item) => item.value === vocalType)?.label ?? 'Automática'
  const langLabel = LANGUAGE_OPTIONS.find((item) => item.value === language)?.label ?? 'Español'

  return (
    <aside
      aria-label="Resumen de creación"
      className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-5 lg:sticky lg:top-5"
    >
      <div className="flex items-start justify-between gap-3 border-b border-border pb-4">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted">Vista previa</p>
          <h2 className="mt-0.5 truncate text-lg font-bold text-white">
            {title.trim() || 'Tu nueva canción'}
          </h2>
        </div>
        <div className="flex shrink-0 items-center gap-1.5 rounded-lg bg-card-hover px-2.5 py-1.5 text-xs">
          <Coins size={14} className="text-primary" aria-hidden="true" />
          <span className="font-bold tabular-nums text-white">{credits}</span>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-1">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted">Modo</dt>
          <dd className="font-semibold text-white">{modeLabel}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted">Duración</dt>
          <dd className="font-semibold text-white">{durationLabel}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted">Voz e idioma</dt>
          <dd className="font-semibold text-white">
            {vocalLabel} · {langLabel}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted">Estilos</dt>
          <dd className="font-semibold text-white">
            {selectedTagCount > 0 ? `${selectedTagCount} seleccionados` : 'Libres'}
          </dd>
        </div>
      </dl>

      <Button
        type="submit"
        form="create-song-form"
        size="lg"
        costCredits={1}
        loading={isBusy}
        disabled={isBusy}
        leftIcon={<Sparkles size={16} aria-hidden="true" />}
        className="w-full"
      >
        {isBusy ? 'Creando tu canción...' : 'Crear canción'}
      </Button>

      {stage !== 'idle' && (
        <div
          role={stage === 'error' || stage === 'no_credits' ? 'alert' : 'status'}
          className={cn(
            'flex flex-col gap-3 rounded-xl border p-4 text-sm',
            stage === 'no_credits' || stage === 'error'
              ? 'border-error-border bg-error-soft text-error'
              : stage === 'ready'
                ? 'border-success/30 bg-success-soft text-success'
                : 'border-primary-border bg-primary-soft text-primary'
          )}
        >
          <div className="flex items-start gap-2.5">
            {isBusy ? (
              <LoaderCircle size={18} className="mt-0.5 shrink-0 animate-spin" aria-hidden="true" />
            ) : stage === 'ready' ? (
              <CheckCircle2 size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
            ) : (
              <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
            )}
            <div className="min-w-0 flex-1 space-y-1">
              <p className="font-semibold">{STAGE_LABELS[stage]}</p>
              {stage === 'polling' && (
                <p className="text-xs text-muted">
                  Puedes seguir navegando; te avisaremos cuando esté lista.
                </p>
              )}
              {stage === 'no_credits' && (
                <p className="text-xs text-white/80">
                  Necesitas al menos 1 crédito para crear una canción.{' '}
                  <Link to="/payments" className="font-semibold text-primary underline">
                    Recargar créditos
                  </Link>
                </p>
              )}
              {stage === 'error' && errorMsg && <p className="text-xs text-white/85">{errorMsg}</p>}
            </div>
          </div>

          {(stage === 'ready' || stage === 'no_credits' || stage === 'error') && (
            <Button variant="secondary" size="sm" onClick={onReset} className="self-start">
              Nueva canción
            </Button>
          )}
        </div>
      )}

      {stage === 'ready' && ready && (
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-3.5">
          {ready.thumbnailUrl && (
            <img
              src={ready.thumbnailUrl}
              alt="Portada de la canción"
              className="aspect-square w-full rounded-lg object-cover"
            />
          )}
          <div className="space-y-1">
            <p className="text-sm font-bold text-white">{title.trim() || 'Tu canción está lista'}</p>
            <p className="text-xs text-muted">
              Guardada en{' '}
              <Link to="/library" className="font-semibold text-primary hover:underline">
                Tu biblioteca
              </Link>
              .
            </p>
          </div>
        </div>
      )}
    </aside>
  )
}

export default CreatePreviewCard
