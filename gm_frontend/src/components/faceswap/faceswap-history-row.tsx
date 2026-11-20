import { LoaderCircle, Trash2, Video } from 'lucide-react'

import { FACESWAP_ACTIVE_STATUSES } from '../../types/faceswap.types'
import type { FaceSwapJob } from '../../types/faceswap.types'
import { BTN_GHOST, STATUS_META, softTone } from './faceswap-ui'

interface Props {
  job: FaceSwapJob
  thumbnailUrl?: string
  selected: boolean
  deleting: boolean
  onSelect: () => void
  onDelete: () => void
}

/** Fila del historial: miniatura, nombre, fecha, estado y borrar. */
export default function FaceSwapHistoryRow({
  job,
  thumbnailUrl,
  selected,
  deleting,
  onSelect,
  onDelete,
}: Props) {
  const active = FACESWAP_ACTIVE_STATUSES.includes(job.status)
  const meta = STATUS_META[job.status]
  const name = job.template?.title || job.source_video_filename || 'Clip propio'

  function handleDelete() {
    if (window.confirm(`¿Borrar "${name}"? Esta acción no se puede deshacer.`)) {
      onDelete()
    }
  }

  return (
    <li
      className="flex items-center gap-2 rounded-lg bg-card pr-2 transition-colors hover:bg-card-hover"
      style={{ outline: selected ? '1px solid var(--color-primary)' : 'none' }}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? 'true' : undefined}
        className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2.5 text-left"
      >
        <span className="flex h-12 w-9 shrink-0 items-center justify-center overflow-hidden rounded bg-card-hover">
          {thumbnailUrl ? (
            <img src={thumbnailUrl} alt="" className="h-full w-full object-cover" />
          ) : (
            <Video size={16} className="text-muted" aria-hidden="true" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-white">{name}</span>
          <span className="block text-xs text-muted">
            {new Date(job.created_at).toLocaleString()}
          </span>
        </span>
        <span
          className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold"
          style={softTone(meta.colorVar)}
        >
          {meta.label}
          {active && ` · ${job.progress_pct}%`}
        </span>
      </button>
      <button
        type="button"
        className={BTN_GHOST}
        onClick={handleDelete}
        disabled={active || deleting}
        aria-label={`Borrar ${name}`}
        title={active ? 'No puedes borrar un video que se está procesando' : 'Borrar'}
      >
        {deleting ? (
          <LoaderCircle size={15} className="animate-spin" aria-hidden="true" />
        ) : (
          <Trash2 size={15} aria-hidden="true" />
        )}
      </button>
    </li>
  )
}
