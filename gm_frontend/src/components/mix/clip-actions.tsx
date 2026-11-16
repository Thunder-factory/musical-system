import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Scissors, Trash2 } from 'lucide-react'
import type { MixClip } from '../../api/modules/mix.api'

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
  const [confirmingDelete, setConfirmingDelete] = useState(false)
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
    setSaving(true)
    setError(null)
    try {
      await onDelete()
      setConfirmingDelete(false)
    } catch {
      setError('No se pudo eliminar el fragmento.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
          paddingTop: 4,
          borderTop: '1px solid var(--border)',
        }}
      >
        <button
          type="button"
          onClick={() => void handleSplit()}
          disabled={!canSplit || saving}
          title={
            canSplit ? 'Dividir en la posición del playhead' : 'Coloca el playhead dentro del clip'
          }
          style={actionButtonStyle(!canSplit || saving)}
        >
          <Scissors size={14} aria-hidden="true" />
          Dividir aquí
        </button>
        {showDelete && onDelete && (
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            disabled={saving}
            title={`Eliminar ${title}`}
            style={{ ...actionButtonStyle(saving), color: 'var(--color-error)' }}
          >
            <Trash2 size={14} aria-hidden="true" />
            Eliminar fragmento
          </button>
        )}
        {playheadMs !== null && (
          <span style={{ alignSelf: 'center', color: 'var(--text-subdued)', fontSize: 11 }}>
            Playhead: {(playheadMs / 1000).toFixed(2)}s
          </span>
        )}
      </div>

      {error && (
        <p role="alert" style={{ margin: 0, color: 'var(--color-error)', fontSize: 12 }}>
          {error}
        </p>
      )}

      {showDelete &&
        onDelete &&
        confirmingDelete &&
        createPortal(
          <div
            role="presentation"
            onClick={() => !saving && setConfirmingDelete(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 120,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 20,
              background: 'var(--overlay)',
            }}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby={`delete-selected-clip-${clip.id}`}
              onClick={(event) => event.stopPropagation()}
              style={{
                width: 'min(100%, 360px)',
                padding: 22,
                borderRadius: 12,
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow)',
              }}
            >
              <h2
                id={`delete-selected-clip-${clip.id}`}
                style={{ margin: '0 0 8px', fontSize: 17 }}
              >
                ¿Eliminar fragmento?
              </h2>
              <p style={{ margin: '0 0 18px', color: 'var(--text-subdued)', fontSize: 13 }}>
                Se quitará “{title}” del mix. La fuente original permanecerá intacta.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setConfirmingDelete(false)}
                  disabled={saving}
                  style={cancelButtonStyle}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void handleDelete()}
                  disabled={saving}
                  style={{
                    ...cancelButtonStyle,
                    border: 'none',
                    background: 'var(--color-error)',
                    color: 'white',
                  }}
                >
                  {saving ? 'Eliminando...' : 'Eliminar'}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </>
  )
}

function actionButtonStyle(disabled: boolean) {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '7px 10px',
    border: '1px solid var(--border)',
    borderRadius: 6,
    background: 'var(--bg-card-hover)',
    color: 'var(--text-base)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: 12,
    fontWeight: 700,
    opacity: disabled ? 0.5 : 1,
  }
}

const cancelButtonStyle = {
  padding: '8px 14px',
  borderRadius: 500,
  border: '1px solid var(--border)',
  background: 'transparent',
  color: 'var(--text-base)',
  cursor: 'pointer',
}
