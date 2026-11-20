import { Check, LoaderCircle } from 'lucide-react'

import { cn } from '../../../lib/cn'
import type { TranslationJob } from '../api/translations.api'
import { stageLabel, TRANSLATION_STAGES } from '../lib/translation-constants'

function ProgressBar({
  label,
  percent,
  tone,
}: {
  label: string
  percent: number
  tone: 'primary' | 'error'
}) {
  const safe = Math.max(0, Math.min(100, Number(percent) || 0))
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <span className={cn('text-sm font-semibold', tone === 'error' ? 'text-error' : 'text-white')}>
          {label}
        </span>
        <span className="text-xs tabular-nums text-muted">{safe}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={safe}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 overflow-hidden rounded-full bg-card-hover"
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            tone === 'error' ? 'bg-error' : 'bg-primary'
          )}
          style={{ width: `${safe}%` }}
        />
      </div>
    </div>
  )
}

export default function TranslationProgress({
  job,
  uploadPercent,
}: {
  job: TranslationJob | null
  uploadPercent: number | null
}) {
  if (uploadPercent !== null) {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4">
        <ProgressBar
          label={`Subiendo tu video… ${uploadPercent}%`}
          percent={uploadPercent}
          tone="primary"
        />
        <p className="text-xs text-muted">Tiempo estimado total: 1–4 minutos.</p>
      </div>
    )
  }

  if (!job || job.status === 'completed') {
    return null
  }

  const failed = job.status === 'failed'
  const currentIndex = TRANSLATION_STAGES.findIndex((stage) => stage.key === job.stage)

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4" aria-live="polite">
      <ProgressBar
        label={failed ? 'La traducción falló' : stageLabel(job.stage)}
        percent={job.progress_pct}
        tone={failed ? 'error' : 'primary'}
      />

      {failed ? (
        job.error_message && (
          <p className="text-xs text-error" role="alert">
            {job.error_message} Tus créditos no fueron cobrados.
          </p>
        )
      ) : (
        <>
          <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Etapas del doblaje">
            {TRANSLATION_STAGES.map((stage, index) => {
              const done = currentIndex > index
              const active = currentIndex === index
              return (
                <li
                  key={stage.key}
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs',
                    active
                      ? 'bg-primary-soft text-white'
                      : done
                        ? 'text-success'
                        : 'text-muted'
                  )}
                >
                  {active ? (
                    <LoaderCircle size={12} className="shrink-0 animate-spin text-primary" aria-hidden="true" />
                  ) : done ? (
                    <Check size={12} className="shrink-0" aria-hidden="true" />
                  ) : (
                    <span aria-hidden="true" className="shrink-0">
                      •
                    </span>
                  )}
                  <span className="truncate">{stage.label}</span>
                </li>
              )
            })}
          </ol>
          <p className="text-xs text-muted">
            Tiempo estimado: 1–4 minutos. Puedes seguir navegando; te avisaremos al terminar.
          </p>
        </>
      )}
    </div>
  )
}
