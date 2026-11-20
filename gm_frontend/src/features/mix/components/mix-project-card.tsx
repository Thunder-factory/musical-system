import { ArrowRight, AudioWaveform, Plus, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge, Button } from '../../../components/ui'
import type { MixProject } from '../api/mix.api'

const STATUS_META: Record<
  MixProject['status'],
  { label: string; variant: 'neutral' | 'warning' | 'success' | 'error' }
> = {
  draft: { label: 'Borrador', variant: 'neutral' },
  processing: { label: 'Procesando', variant: 'warning' },
  ready: { label: 'Listo', variant: 'success' },
  failed: { label: 'Error', variant: 'error' },
}

interface MixProjectCardProps {
  project: MixProject
  pendingSongId?: string | null
  onDelete: (project: MixProject) => void
  onAddSongToProject?: (projectId: string) => void
}

export default function MixProjectCard({
  project,
  pendingSongId,
  onDelete,
  onAddSongToProject,
}: MixProjectCardProps) {
  const meta = STATUS_META[project.status] ?? { label: project.status, variant: 'neutral' as const }

  return (
    <article className="flex flex-col rounded-xl border border-border bg-card p-4 transition-all hover:border-border-strong hover:bg-card-hover">
      <div className="mb-3 flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--gradient-primary)] text-black">
          <AudioWaveform size={20} aria-hidden="true" />
        </div>
        <button
          type="button"
          onClick={() => onDelete(project)}
          aria-label={`Eliminar ${project.title}`}
          title="Eliminar proyecto"
          className="rounded-md p-1.5 text-muted transition-colors hover:bg-error-soft hover:text-error"
        >
          <Trash2 size={15} aria-hidden="true" />
        </button>
      </div>

      <Link
        to={`/mix/${project.id}`}
        className="truncate text-base font-bold text-white hover:text-primary"
      >
        {project.title}
      </Link>

      <p className="mt-1 text-xs text-muted">
        {project.clip_count} clip{project.clip_count !== 1 ? 's' : ''}
        {project.bpm ? ` · ${project.bpm} BPM` : ''}
        {project.duration_seconds
          ? ` · ${Math.floor(project.duration_seconds / 60)}:${String(project.duration_seconds % 60).padStart(2, '0')}`
          : ''}
      </p>

      <div className="mt-4 flex items-center justify-between gap-2 pt-1">
        <Badge variant={meta.variant}>{meta.label}</Badge>

        {pendingSongId && onAddSongToProject ? (
          <Button
            variant="primary"
            size="sm"
            leftIcon={<Plus size={13} />}
            onClick={() => onAddSongToProject(project.id)}
          >
            Añadir aquí
          </Button>
        ) : (
          <Link
            to={`/mix/${project.id}`}
            className="inline-flex items-center gap-1 text-xs font-bold text-primary hover:text-primary-hover"
          >
            Abrir
            <ArrowRight size={13} aria-hidden="true" />
          </Link>
        )}
      </div>
    </article>
  )
}
