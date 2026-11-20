import { useState } from 'react'
import { Scissors, Trash2 } from 'lucide-react'

import { Button, Modal } from '../../../components/ui'
import type { MixClip } from '../api/mix.api'

interface ClipContextDialogProps {
  open: boolean
  clip: MixClip
  playheadMs: number | null
  onSplit: () => Promise<void>
  onDelete: () => Promise<void>
  onClose: () => void
}

function formatTime(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export default function ClipContextDialog({
  open,
  clip,
  playheadMs,
  onSplit,
  onDelete,
  onClose,
}: ClipContextDialogProps) {
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
      onClose()
    } catch {
      setError('No se pudo dividir el clip.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setSaving(true)
    setError(null)
    try {
      await onDelete()
      onClose()
    } catch {
      setError('No se pudo eliminar el fragmento.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={title} size="sm" preventClose={saving}>
      <div className="flex flex-col gap-4">
        <p className="text-xs text-muted">
          {clip.is_external ? 'Archivo externo · ' : ''}Clip {clip.position + 1} · Cabezal{' '}
          {formatTime(playheadMs ?? 0)}
        </p>

        <div className="grid grid-cols-2 gap-2.5">
          <Button
            variant="secondary"
            leftIcon={<Scissors size={14} />}
            disabled={!canSplit || saving}
            title={
              canSplit ? 'Dividir en el cabezal' : 'El cabezal debe estar dentro del clip'
            }
            onClick={() => void handleSplit()}
          >
            Dividir
          </Button>
          <Button
            variant="danger"
            leftIcon={<Trash2 size={14} />}
            disabled={saving}
            onClick={() => void handleDelete()}
          >
            {saving ? 'Eliminando...' : 'Eliminar'}
          </Button>
        </div>

        {error && (
          <p role="alert" className="text-xs text-error">
            {error}
          </p>
        )}
      </div>
    </Modal>
  )
}
