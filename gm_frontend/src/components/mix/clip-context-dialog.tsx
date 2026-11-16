import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Scissors, Trash2, X } from 'lucide-react'
import type { MixClip } from '../../api/modules/mix.api'

interface ClipContextDialogProps {
  clip: MixClip
  playheadMs: number | null
  onSplit: () => Promise<void>
  onDelete: () => Promise<void>
  onClose: () => void
}

export default function ClipContextDialog({
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

  function formatTime(milliseconds: number) {
    const seconds = Math.max(0, Math.floor(milliseconds / 1000))
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
  }

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

  return createPortal(
    <div role="presentation" onClick={() => !saving && onClose()} style={overlayStyle}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`clip-context-${clip.id}`}
        onClick={(event) => event.stopPropagation()}
        style={dialogStyle}
      >
        <div style={headerStyle}>
          <div style={{ minWidth: 0 }}>
            <h2 id={`clip-context-${clip.id}`} style={titleStyle} title={title}>
              {title}
            </h2>
            <span style={metaStyle}>
              {clip.is_external ? 'Archivo externo · ' : ''}Clip {clip.position + 1} ·
              Playhead {formatTime(playheadMs ?? 0)}
            </span>
          </div>
          <button type="button" onClick={onClose} disabled={saving} style={closeButtonStyle}>
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        <div style={actionsStyle}>
          <button
            type="button"
            onClick={() => void handleSplit()}
            disabled={!canSplit || saving}
            title={canSplit ? 'Dividir en el playhead' : 'El playhead debe estar dentro del clip'}
            style={actionButtonStyle(!canSplit || saving)}
          >
            <Scissors size={15} aria-hidden="true" />
            <strong>Dividir</strong>
          </button>
          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={saving}
            style={{ ...actionButtonStyle(saving), color: 'var(--color-error)' }}
          >
            <Trash2 size={15} aria-hidden="true" />
            <strong>{saving ? 'Eliminando...' : 'Eliminar'}</strong>
          </button>
        </div>

        {error && (
          <p role="alert" style={errorStyle}>
            {error}
          </p>
        )}
      </div>
    </div>,
    document.body
  )
}

const overlayStyle = {
  position: 'fixed' as const,
  inset: 0,
  zIndex: 320,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 20,
  background: 'var(--overlay)',
}

const dialogStyle = {
  width: 'min(100%, 380px)',
  padding: 20,
  borderRadius: 12,
  background: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  boxShadow: 'var(--shadow)',
}

const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: 12,
  alignItems: 'flex-start',
}
const titleStyle = {
  margin: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap' as const,
  fontSize: 16,
  fontWeight: 700,
}
const metaStyle = { display: 'block', marginTop: 4, color: 'var(--text-subdued)', fontSize: 11 }
const closeButtonStyle = {
  display: 'inline-flex',
  padding: 5,
  border: 'none',
  borderRadius: 6,
  background: 'transparent',
  color: 'var(--text-subdued)',
  cursor: 'pointer',
}
const actionsStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 16 }
const actionButtonStyle = (disabled: boolean) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 10,
  width: '100%',
  padding: '9px 10px',
  border: '1px solid var(--border)',
  borderRadius: 8,
  background: 'var(--bg-card-hover)',
  color: 'var(--text-base)',
  cursor: disabled ? 'not-allowed' : 'pointer',
  textAlign: 'left' as const,
  opacity: disabled ? 0.5 : 1,
})
const errorStyle = { margin: '12px 0 0', color: 'var(--color-error)', fontSize: 12 }
