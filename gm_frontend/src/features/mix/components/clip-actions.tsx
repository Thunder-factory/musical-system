import { useState } from 'react'
import { Scissors, Trash2 } from 'lucide-react'

import { Button, useConfirm } from '../../../components/ui'
import type { MixClip } from '../api/mix.api'

interface ClipActionsProps {
  clip: MixClip
  playheadMs: number | null
  onSplit: () => Promise<void>
  onDelete?: () => Promise<void>
  showDelete?: boolean
}

export default function ClipActions({
  clip,
  playheadMs,
  onSplit,
  onDelete,
  showDelete = true,
}: ClipActionsProps) {
  const confirm = useConfirm()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const clipEndMs = clip.timeline_start_ms + clip.duration_ms
  const canSplit =
    playheadMs !== null && playheadMs > clip.timeline_start_ms && playheadMs < clipEndMs
  const title = clip.custom_audio_name ?? clip.song_detail?.title ?? `Clip #${clip.position + 1}`

  async function handleSplit() {
    if (!canSplit) {
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSplit()
    } catch {
      setError('No se pudo dividir el clip.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!onDelete) {
      return
    }
    const accepted = await confirm({
      title: '¿Eliminar fragmento?',
      description: `Se quitará “${title}” del mix. La fuente original permanecerá intacta.`,
      confirmLabel: 'Eliminar',
      variant: 'danger',
    })
    if (!accepted) {
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onDelete()
    } catch {
      setError('No se pudo eliminar el fragmento.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-2 border-t border-border pt-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Scissors size={14} />}
          disabled={!canSplit || saving}
          title={
            canSplit ? 'Dividir en la posición del cabezal' : 'Coloca el cabezal dentro del clip'
          }
          onClick={() => void handleSplit()}
        >
          Dividir aquí
        </Button>

        {showDelete && onDelete && (
          <Button
            variant="danger"
            size="sm"
            leftIcon={<Trash2 size={14} />}
            disabled={saving}
            onClick={() => void handleDelete()}
          >
            Eliminar fragmento
          </Button>
        )}

        {playheadMs !== null && (
          <span className="text-[11px] tabular-nums text-muted">
            Cabezal: {(playheadMs / 1000).toFixed(2)}s
          </span>
        )}
      </div>

      {error && (
        <p role="alert" className="text-xs text-error">
          {error}
        </p>
      )}
    </div>
  )
}
