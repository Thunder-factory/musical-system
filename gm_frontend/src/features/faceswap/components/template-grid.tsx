import { Clapperboard, RotateCw, Upload } from 'lucide-react'

import { Button } from '../../../components/ui'
import type { FaceSwapTemplate } from '../types/faceswap.types'
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
          <div key={i} className="flex flex-col gap-2 rounded-xl bg-card-hover p-1.5">
            <div className="aspect-[9/16] w-full animate-pulse rounded-md bg-surface" />
            <div className="mx-1 mb-1 h-3 w-2/3 animate-pulse rounded bg-surface" />
          </div>
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl bg-card-hover px-4 py-8 text-center">
        <p className="text-sm text-error">{errorMessage ?? 'No se pudieron cargar las plantillas.'}</p>
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="secondary" size="sm" onClick={onRetry} leftIcon={<RotateCw size={14} />}>
            Reintentar
          </Button>
          <Button variant="secondary" size="sm" onClick={onUseOwnClip} leftIcon={<Upload size={14} />}>
            Subir mi clip
          </Button>
        </div>
      </div>
    )
  }

  if (templates.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl bg-card-hover px-4 py-8 text-center">
        <Clapperboard size={28} className="text-muted" aria-hidden="true" />
        <p className="text-sm text-muted">Aún no hay plantillas. Sube tu propio clip.</p>
        <Button variant="secondary" size="sm" onClick={onUseOwnClip} leftIcon={<Upload size={14} />}>
          Subir mi clip
        </Button>
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
