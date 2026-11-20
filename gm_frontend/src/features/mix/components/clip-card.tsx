import { useState } from 'react'
import { Pause, Play, Scissors, Trash2, Volume2, VolumeX } from 'lucide-react'

import { Badge, useConfirm } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { deleteClip, type MixClip } from '../api/mix.api'

interface ClipCardProps {
  clip: MixClip
  mixId: string
  isSelected: boolean
  onSelect: () => void
  onDelete: () => void
  isPlaying: boolean
  timelinePositionMs: number
  muted: boolean
  solo: boolean
  onTogglePlay: () => void
  onToggleMute: () => void
  onToggleSolo: () => void
}

function fmt(sec: number) {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatPreciseSeconds(sec: number) {
  return `${sec.toFixed(2)}s`
}

export default function ClipCard({
  clip,
  mixId,
  isSelected,
  onSelect,
  onDelete,
  isPlaying,
  timelinePositionMs,
  muted,
  solo,
  onTogglePlay,
  onToggleMute,
  onToggleSolo,
}: ClipCardProps) {
  const confirm = useConfirm()
  const [deleting, setDeleting] = useState(false)
  const title = clip.custom_audio_name ?? clip.song_detail?.title ?? `Clip #${clip.position + 1}`

  const startSec = clip.start_time_ms / 1000
  const endSec = clip.end_time_ms / 1000
  const clipDuration = Math.max(endSec - startSec, 0.1)
  const clipOffsetMs = Math.max(
    0,
    Math.min(timelinePositionMs - clip.timeline_start_ms, clip.duration_ms)
  )
  const elapsed = Math.max(0, clipOffsetMs / 1000)
  const progress = clipDuration > 0 ? Math.min(elapsed / clipDuration, 1) : 0

  async function handleDelete() {
    const accepted = await confirm({
      title: '¿Eliminar clip?',
      description: `Se quitará “${title}” de este mix.`,
      confirmLabel: 'Eliminar',
      variant: 'danger',
    })
    if (!accepted) {
      return
    }
    setDeleting(true)
    try {
      await deleteClip(mixId, clip.id)
      onDelete()
    } catch {
      toast.error('No se pudo eliminar el clip')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div
      className={`rounded-lg border p-3.5 transition-colors ${
        isSelected ? 'border-primary bg-primary-subtle' : 'border-border bg-card'
      }`}
    >
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onSelect}
          className="flex min-w-0 items-center gap-2 text-left"
        >
          <span
            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-card-hover text-[10px] font-bold ${
              isSelected ? 'text-primary' : 'text-muted'
            }`}
          >
            {clip.position + 1}
          </span>
          <span className="max-w-[160px] truncate text-xs font-semibold text-white">{title}</span>
          {clip.is_external && <Badge variant="primary">Externo</Badge>}
        </button>

        <button
          type="button"
          onClick={() => void handleDelete()}
          disabled={deleting}
          aria-label={`Eliminar ${title}`}
          title="Eliminar clip"
          className="rounded p-1 text-muted transition-colors hover:bg-error-soft hover:text-error disabled:opacity-50"
        >
          <Trash2 size={14} aria-hidden="true" />
        </button>
      </div>

      <div className="flex items-center gap-2 rounded-md bg-card px-2.5 py-1.5">
        <button
          type="button"
          onClick={onTogglePlay}
          aria-label={isPlaying ? `Pausar ${title}` : `Reproducir ${title}`}
          className="flex shrink-0 items-center text-white hover:text-primary"
        >
          {isPlaying ? (
            <Pause size={16} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={16} fill="currentColor" aria-hidden="true" />
          )}
        </button>

        <span className="min-w-[32px] shrink-0 text-[11px] tabular-nums text-white/75">
          {fmt(elapsed)}
        </span>

        <div className="relative h-1 flex-1 rounded bg-border-strong">
          <div
            className="absolute inset-y-0 left-0 rounded bg-white"
            style={{ width: `${progress * 100}%` }}
          />
        </div>

        <span className="min-w-[32px] shrink-0 text-[11px] tabular-nums text-muted">
          {fmt(clipDuration)}
        </span>

        {muted ? (
          <VolumeX size={14} className="shrink-0 text-error" aria-hidden="true" />
        ) : (
          <Volume2 size={14} className="shrink-0 text-muted" aria-hidden="true" />
        )}

        <div className="ml-auto flex shrink-0 gap-1">
          <button
            type="button"
            aria-pressed={muted}
            aria-label={muted ? `Activar sonido de ${title}` : `Silenciar ${title}`}
            onClick={onToggleMute}
            className={`h-5 w-5 rounded border text-[10px] font-extrabold ${
              muted
                ? 'border-error-border bg-error-soft text-error'
                : 'border-border text-muted hover:text-white'
            }`}
          >
            M
          </button>
          <button
            type="button"
            aria-pressed={solo}
            aria-label={`${solo ? 'Desactivar' : 'Activar'} solo para ${title}`}
            onClick={onToggleSolo}
            className={`h-5 w-5 rounded border text-[10px] font-extrabold ${
              solo
                ? 'border-primary bg-primary-subtle text-primary'
                : 'border-border text-muted hover:text-white'
            }`}
          >
            S
          </button>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-1.5 truncate text-[10px] font-bold text-primary">
        <Scissors size={12} aria-hidden="true" />
        <span>
          Recorte: {formatPreciseSeconds(clipDuration)} · {formatPreciseSeconds(startSec)}–
          {formatPreciseSeconds(endSec)}
        </span>
      </div>
    </div>
  )
}
