import { LoaderCircle, Trash2, Video } from 'lucide-react'

import { Badge, useConfirm, type BadgeVariant } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import {
  FACESWAP_ACTIVE_STATUSES,
  type FaceSwapJob,
  type FaceSwapStatus,
} from '../types/faceswap.types'

interface Props {
  job: FaceSwapJob
  thumbnailUrl?: string
  selected: boolean
  deleting: boolean
  onSelect: () => void
  onDelete: () => void
}

const STATUS_BADGES: Record<FaceSwapStatus, { label: string; variant: BadgeVariant }> = {
  queued: { label: 'En cola', variant: 'warning' },
  processing: { label: 'Procesando', variant: 'warning' },
  completed: { label: 'Completado', variant: 'success' },
  failed: { label: 'Error', variant: 'error' },
}

export default function FaceSwapHistoryRow({
  job,
  thumbnailUrl,
  selected,
  deleting,
  onSelect,
  onDelete,
}: Props) {
  const confirm = useConfirm()
  const active = FACESWAP_ACTIVE_STATUSES.includes(job.status)
  const meta = STATUS_BADGES[job.status]
  const name = job.template?.title || job.source_video_filename || 'Clip propio'

  async function handleDelete() {
    const ok = await confirm({
      title: 'Borrar video',
      description: `¿Seguro que deseas borrar "${name}"? Esta acción no se puede deshacer.`,
      confirmLabel: 'Borrar',
      variant: 'danger',
    })
    if (ok) {
      onDelete()
    }
  }

  return (
    <li
      className={cn(
        'flex items-center gap-2 rounded-xl border bg-card pr-2 transition-colors hover:bg-card-hover',
        selected ? 'border-primary' : 'border-transparent'
      )}
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
        <Badge variant={meta.variant}>
          {meta.label}
          {active && ` · ${job.progress_pct}%`}
        </Badge>
      </button>

      <button
        type="button"
        onClick={() => void handleDelete()}
        disabled={active || deleting}
        aria-label={`Borrar ${name}`}
        title={active ? 'No puedes borrar un video que se está procesando' : 'Borrar'}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-error-soft hover:text-error disabled:cursor-not-allowed disabled:opacity-40"
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
