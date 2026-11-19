import { Clapperboard, RotateCw, Upload } from 'lucide-react'

import type { FaceSwapTemplate } from '../../types/faceswap.types'
import { BTN_OUTLINE } from './faceswap-ui'
import TemplateCard from './template-card'

interface Props {
  templates: FaceSwapTemplate[]
  isLoading: boolean
  isError: boolean
  errorMessage?: string
  selectedId: string | null
  onSelect: (id: string) => void
  onRetry: () => void
  onUseOwnClip: () => void
  disabled?: boolean
}

const GRID = 'grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4'

/** Grilla del catálogo de plantillas con estados cargando, error y vacío. */
export default function TemplateGrid({
  templates,
  isLoading,
  isError,
  errorMessage,
  selectedId,
  onSelect,
  onRetry,
  onUseOwnClip,
  disabled = false,
}: Props) {
  if (isLoading) {
    return (
      <div className={GRID} aria-busy="true" aria-label="Cargando plantillas">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="flex flex-col gap-2 rounded-lg bg-card-hover p-1.5">
            <div className="aspect-[9/16] w-full animate-pulse rounded-md bg-surface" />
            <div className="mx-1 mb-1 h-3 w-2/3 animate-pulse rounded bg-surface" />
          </div>
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg bg-card-hover px-4 py-8 text-center">
        <p className="text-sm" style={{ color: 'var(--color-error)' }}>
          {errorMessage ?? 'No se pudieron cargar las plantillas.'}
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          <button type="button" className={BTN_OUTLINE} onClick={onRetry}>
            <RotateCw size={14} aria-hidden="true" />
            Reintentar
          </button>
          <button type="button" className={BTN_OUTLINE} onClick={onUseOwnClip}>
            <Upload size={14} aria-hidden="true" />
            Subir mi clip
          </button>
        </div>
      </div>
    )
  }

  if (templates.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg bg-card-hover px-4 py-8 text-center">
        <Clapperboard size={28} className="text-muted" aria-hidden="true" />
        <p className="text-sm text-muted">Aún no hay plantillas. Sube tu propio clip.</p>
        <button type="button" className={BTN_OUTLINE} onClick={onUseOwnClip}>
          <Upload size={14} aria-hidden="true" />
          Subir mi clip
        </button>
      </div>
    )
  }

  return (
    <div className={GRID}>
      {templates.map((template) => (
        <TemplateCard
          key={template.id}
          template={template}
          selected={template.id === selectedId}
          onSelect={() => onSelect(template.id)}
          disabled={disabled}
        />
      ))}
    </div>
  )
}
