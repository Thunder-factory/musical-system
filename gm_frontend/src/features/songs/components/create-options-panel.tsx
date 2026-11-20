import { useState } from 'react'
import { ChevronDown, SlidersHorizontal } from 'lucide-react'

import { Select } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import {
  DURATION_OPTIONS,
  LANGUAGE_OPTIONS,
  VOCAL_OPTIONS,
  type SongLanguage,
  type VocalType,
} from '../lib/create-song-options'

interface CreateOptionsPanelProps {
  duration: number
  vocalType: VocalType
  language: SongLanguage
  guidanceScale: number
  inferStep: number
  disabled?: boolean
  onDurationChange: (value: number) => void
  onVocalTypeChange: (value: VocalType) => void
  onLanguageChange: (value: SongLanguage) => void
  onGuidanceScaleChange: (value: number) => void
  onInferStepChange: (value: number) => void
}

export function CreateOptionsPanel({
  duration,
  vocalType,
  language,
  guidanceScale,
  inferStep,
  disabled = false,
  onDurationChange,
  onVocalTypeChange,
  onLanguageChange,
  onGuidanceScaleChange,
  onInferStepChange,
}: CreateOptionsPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Select
          label="Duración"
          value={String(duration)}
          options={DURATION_OPTIONS}
          disabled={disabled}
          onChange={(value) => onDurationChange(Number(value))}
        />
        <Select
          label="Tipo de voz"
          value={vocalType}
          options={VOCAL_OPTIONS}
          disabled={disabled}
          onChange={(value) => onVocalTypeChange(value as VocalType)}
        />
        <Select
          label="Idioma"
          value={language}
          options={LANGUAGE_OPTIONS}
          disabled={disabled}
          onChange={(value) => onLanguageChange(value as SongLanguage)}
        />
      </div>

      <div className="border-t border-border pt-2.5">
        <button
          type="button"
          aria-expanded={showAdvanced}
          onClick={() => setShowAdvanced((prev) => !prev)}
          className="inline-flex items-center gap-2 text-xs font-semibold text-muted transition-colors hover:text-white"
        >
          <SlidersHorizontal size={14} aria-hidden="true" />
          Ajustes avanzados
          <ChevronDown
            size={14}
            aria-hidden="true"
            className={cn('transition-transform', showAdvanced && 'rotate-180')}
          />
        </button>

        {showAdvanced && (
          <div className="mt-3 grid grid-cols-1 gap-4 rounded-lg bg-card-hover p-3.5 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs">
                <label htmlFor="guidance-scale" className="font-semibold text-white">
                  Fidelidad al prompt
                </label>
                <span className="tabular-nums text-muted">{guidanceScale}</span>
              </div>
              <input
                id="guidance-scale"
                type="range"
                min={1}
                max={30}
                step={0.5}
                value={guidanceScale}
                disabled={disabled}
                onChange={(e) => onGuidanceScaleChange(Number(e.target.value))}
                className="accent-[var(--color-primary)]"
              />
              <p className="text-[11px] text-muted">
                Valores más altos siguen tu descripción de forma más estricta.
              </p>
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs">
                <label htmlFor="infer-step" className="font-semibold text-white">
                  Pasos de refinado
                </label>
                <span className="tabular-nums text-muted">{inferStep}</span>
              </div>
              <input
                id="infer-step"
                type="range"
                min={20}
                max={200}
                step={5}
                value={inferStep}
                disabled={disabled}
                onChange={(e) => onInferStepChange(Number(e.target.value))}
                className="accent-[var(--color-primary)]"
              />
              <p className="text-[11px] text-muted">
                Más pasos refinan el detalle de la mezcla (por defecto 100).
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default CreateOptionsPanel
