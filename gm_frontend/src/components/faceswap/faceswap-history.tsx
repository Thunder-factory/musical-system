import type { FaceSwapJob, FaceSwapTemplate } from '../../types/faceswap.types'
import FaceSwapEmptyState from './faceswap-empty-state'
import FaceSwapHistoryRow from './faceswap-history-row'

interface Props {
  jobs: FaceSwapJob[]
  templates: FaceSwapTemplate[]
  isLoading: boolean
  activeJobId: string | null
  deletingId: string | null
  error: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onStart: () => void
}

/** Historial "Mis videos" con estados cargando, vacío y error de borrado. */
export default function FaceSwapHistory({
  jobs,
  templates,
  isLoading,
  activeJobId,
  deletingId,
  error,
  onSelect,
  onDelete,
  onStart,
}: Props) {
  const thumbs = new Map(templates.map((t) => [t.id, t.thumbnail_url]))

  return (
    <section className="flex flex-col gap-3" aria-labelledby="faceswap-history-title">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="faceswap-history-title" className="text-xl font-bold text-white">
          Mis videos
        </h2>
        {jobs.length > 0 && <span className="text-xs text-muted">{jobs.length} en total</span>}
      </div>

      {error && (
        <p className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}

      {isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-[68px] animate-pulse rounded-lg bg-card" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <FaceSwapEmptyState onStart={onStart} />
      ) : (
        <ul className="grid gap-2 lg:grid-cols-2">
          {jobs.map((job) => (
            <FaceSwapHistoryRow
              key={job.id}
              job={job}
              thumbnailUrl={job.template ? thumbs.get(job.template.id) : undefined}
              selected={job.id === activeJobId}
              deleting={job.id === deletingId}
              onSelect={() => onSelect(job.id)}
              onDelete={() => onDelete(job.id)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
