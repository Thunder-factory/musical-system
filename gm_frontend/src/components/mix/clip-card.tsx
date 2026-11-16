// src/components/mix/clip-card.tsx
import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Pause, Play, Scissors, Trash2, Volume2, VolumeX } from 'lucide-react'
import type { MixClip } from '../../api/modules/mix.api'
import { deleteClip } from '../../api/modules/mix.api'

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
  const isExternal = clip.is_external
  const title = clip.custom_audio_name ?? clip.song_detail?.title ?? `Clip #${clip.position + 1}`

  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const startSec = clip.start_time_ms / 1000
  const endSec = clip.end_time_ms / 1000
  const clipDuration = Math.max(endSec - startSec, 0.1)
  const clipOffsetMs = Math.max(
    0,
    Math.min(timelinePositionMs - clip.timeline_start_ms, clip.duration_ms)
  )
  const currentSec = startSec + clipOffsetMs / 1000
  const progress = clipDuration > 0 ? Math.min(clipOffsetMs / 1000 / clipDuration, 1) : 0

  async function confirmDelete() {
    setDeleting(true)
    try {
      await deleteClip(mixId, clip.id)
      onDelete()
      setConfirmingDelete(false)
    } catch {
      /* silencioso */
    } finally {
      setDeleting(false)
    }
  }

  const elapsed = Math.max(0, currentSec - startSec)

  return (
    <div
      onClick={onSelect}
      style={{
        background: isSelected ? 'var(--color-primary-subtle)' : 'var(--bg-card)',
        border: `1px solid ${isSelected ? 'var(--color-primary)' : 'var(--border)'}`,
        borderRadius: 8,
        padding: '12px 14px',
        cursor: 'pointer',
        transition: 'all 0.15s',
        boxShadow: isSelected ? '0 0 0 1px var(--color-primary-border)' : 'none',
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span
            style={{
              width: 22,
              height: 22,
              borderRadius: '50%',
              background: 'var(--bg-card-hover)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              fontWeight: 700,
              flexShrink: 0,
              color: isSelected ? 'var(--color-primary)' : 'var(--text-subdued)',
            }}
          >
            {clip.position + 1}
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--text-base)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: 120,
            }}
          >
            {title}
          </span>
          {isExternal && (
            <span
              style={{
                flexShrink: 0,
                padding: '2px 5px',
                borderRadius: 4,
                background: 'var(--bg-card-hover)',
                color: 'var(--color-info)',
                fontSize: 9,
                fontWeight: 700,
              }}
            >
              EXTERNO
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            setConfirmingDelete(true)
          }}
          aria-label={`Eliminar ${title}`}
          title="Eliminar clip"
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--color-error)'
            e.currentTarget.style.background = 'var(--color-error-soft)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--text-subdued)'
            e.currentTarget.style.background = 'none'
          }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-subdued)',
            padding: 5,
            borderRadius: 5,
            transition: 'color 0.15s, background 0.15s',
          }}
        >
          <Trash2 size={14} aria-hidden="true" />
        </button>
      </div>

      {/* ── Player bar ── */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: 'var(--bg-card)',
          borderRadius: 6,
          padding: '6px 10px',
        }}
      >
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onTogglePlay()
          }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-base)',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            flexShrink: 0,
          }}
        >
          {isPlaying ? (
            <Pause size={18} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={18} fill="currentColor" aria-hidden="true" />
          )}
        </button>

        <span
          style={{
            fontSize: 11,
            color: 'var(--text-base-soft)',
            flexShrink: 0,
            minWidth: 32,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {fmt(elapsed)}
        </span>

        <div
          style={{
            flex: 1,
            height: 4,
            borderRadius: 2,
            background: 'var(--border-strong)',
            cursor: 'default',
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              bottom: 0,
              width: `${progress * 100}%`,
              background: 'var(--text-base)',
              borderRadius: 2,
              transition: isPlaying ? 'none' : 'width 0.1s',
            }}
          />
          <div
            style={{
              position: 'absolute',
              top: '50%',
              transform: 'translate(-50%, -50%)',
              left: `${progress * 100}%`,
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: 'var(--text-base)',
              boxShadow: '0 0 0 2px var(--bg-white-soft)',
              pointerEvents: 'none',
            }}
          />
        </div>

        <span
          style={{
            fontSize: 11,
            color: 'var(--text-subdued)',
            flexShrink: 0,
            minWidth: 32,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {fmt(clipDuration)}
        </span>

        {muted ? (
          <VolumeX
            size={14}
            aria-hidden="true"
            style={{ color: 'var(--color-error)', flexShrink: 0 }}
          />
        ) : (
          <Volume2
            size={14}
            aria-hidden="true"
            style={{ color: 'var(--text-subdued)', flexShrink: 0 }}
          />
        )}

        <div style={{ display: 'flex', gap: 3, marginLeft: 'auto', flexShrink: 0 }}>
          <button
            type="button"
            aria-pressed={muted}
            aria-label={muted ? `Activar sonido de ${title}` : `Silenciar ${title}`}
            title={muted ? 'Activar sonido' : 'Silenciar'}
            onClick={(e) => {
              e.stopPropagation()
              onToggleMute()
            }}
            style={{
              width: 22,
              height: 22,
              padding: 0,
              borderRadius: 4,
              border: '1px solid var(--border)',
              background: muted ? 'var(--color-error-soft)' : 'transparent',
              color: muted ? 'var(--color-error)' : 'var(--text-subdued)',
              cursor: 'pointer',
              fontSize: 10,
              fontWeight: 800,
              lineHeight: 1,
            }}
          >
            M
          </button>
          <button
            type="button"
            aria-pressed={solo}
            aria-label={`${solo ? 'Desactivar' : 'Activar'} solo visual para ${title}`}
            title="Solo (visual)"
            onClick={(e) => {
              e.stopPropagation()
              onToggleSolo()
            }}
            style={{
              width: 22,
              height: 22,
              padding: 0,
              borderRadius: 4,
              border: '1px solid var(--border)',
              background: solo ? 'var(--color-primary-subtle)' : 'transparent',
              color: solo ? 'var(--color-primary)' : 'var(--text-subdued)',
              cursor: 'pointer',
              fontSize: 10,
              fontWeight: 800,
              lineHeight: 1,
            }}
          >
            S
          </button>
        </div>
      </div>

      <div
        title={`${formatPreciseSeconds(clipDuration)} · ${formatPreciseSeconds(startSec)}–${formatPreciseSeconds(endSec)}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          minWidth: 0,
          marginTop: 8,
          color: 'var(--color-primary)',
          fontSize: 10,
          fontWeight: 700,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        <Scissors size={12} aria-hidden="true" />
        Recorte: {formatPreciseSeconds(clipDuration)} · {formatPreciseSeconds(startSec)}–
        {formatPreciseSeconds(endSec)}
      </div>

      {confirmingDelete &&
        createPortal(
          <div
            role="presentation"
            onClick={() => !deleting && setConfirmingDelete(false)}
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
              aria-labelledby={`delete-clip-title-${clip.id}`}
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
                id={`delete-clip-title-${clip.id}`}
                style={{ margin: '0 0 8px', fontSize: 17, fontWeight: 700 }}
              >
                ¿Eliminar clip?
              </h2>
              <p style={{ margin: '0 0 18px', fontSize: 13, color: 'var(--text-subdued)' }}>
                Se quitará “{title}” de este mix.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setConfirmingDelete(false)}
                  disabled={deleting}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 500,
                    border: '1px solid var(--border)',
                    background: 'transparent',
                    color: 'var(--text-base)',
                    cursor: 'pointer',
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void confirmDelete()}
                  disabled={deleting}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 500,
                    border: 'none',
                    background: 'var(--color-error)',
                    color: 'white',
                    fontWeight: 700,
                    cursor: 'pointer',
                    opacity: deleting ? 0.6 : 1,
                  }}
                >
                  {deleting ? 'Eliminando...' : 'Eliminar'}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  )
}
