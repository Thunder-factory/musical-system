// src/components/mix/clip-card.tsx
import { useEffect, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { LoaderCircle, Pause, Play, Scissors, Trash2, Volume2 } from 'lucide-react'
import type { MixClip } from '../../api/modules/mix.api'
import { deleteClip } from '../../api/modules/mix.api'
import { getSongPlayUrl } from '../../api/modules/songs.api'

export function ClipTimeInputs({
  clip,
  onCommit,
}: {
  clip: MixClip
  onCommit: (field: string, value: number) => void
}) {
  const [startDraft, setStartDraft] = useState(formatInputSeconds(clip.start_time_ms))
  const [endDraft, setEndDraft] = useState(formatInputSeconds(clip.end_time_ms))

  useEffect(() => {
    setStartDraft(formatInputSeconds(clip.start_time_ms))
    setEndDraft(formatInputSeconds(clip.end_time_ms))
  }, [clip.start_time_ms, clip.end_time_ms])

  function commitStart() {
    const seconds = Number(startDraft)
    if (!Number.isFinite(seconds)) {
      setStartDraft(formatInputSeconds(clip.start_time_ms))
      return
    }
    const milliseconds = Math.round(
      Math.min(Math.max(seconds, 0), (clip.end_time_ms - 100) / 1000) * 1000
    )
    setStartDraft(formatInputSeconds(milliseconds))
    if (milliseconds !== clip.start_time_ms) onCommit('start_time_ms', milliseconds)
  }

  function commitEnd() {
    const seconds = Number(endDraft)
    if (!Number.isFinite(seconds)) {
      setEndDraft(formatInputSeconds(clip.end_time_ms))
      return
    }
    const milliseconds = Math.round(Math.max(seconds, (clip.start_time_ms + 100) / 1000) * 1000)
    setEndDraft(formatInputSeconds(milliseconds))
    if (milliseconds !== clip.end_time_ms) onCommit('end_time_ms', milliseconds)
  }

  return (
    <div style={{ display: 'flex', gap: 10 }}>
      <label
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          gap: 4,
          fontSize: 12,
          color: 'var(--text-subdued)',
        }}
      >
        Inicio (s)
        <input
          type="number"
          min="0"
          step="0.01"
          value={startDraft}
          onChange={(e) => setStartDraft(e.target.value)}
          onBlur={(e) => {
            commitStart()
            e.currentTarget.style.borderColor = 'var(--border)'
          }}
          onKeyDown={(e) => e.key === 'Enter' && commitStart()}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-primary)'
          }}
          style={{
            background: 'var(--bg-card-hover)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '8px 10px',
            color: 'var(--text-base)',
            fontSize: 13,
            width: '100%',
            boxSizing: 'border-box',
            outline: 'none',
          }}
        />
      </label>
      <label
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          gap: 4,
          fontSize: 12,
          color: 'var(--text-subdued)',
        }}
      >
        Fin (s)
        <input
          type="number"
          min="0"
          step="0.01"
          value={endDraft}
          onChange={(e) => setEndDraft(e.target.value)}
          onBlur={(e) => {
            commitEnd()
            e.currentTarget.style.borderColor = 'var(--border)'
          }}
          onKeyDown={(e) => e.key === 'Enter' && commitEnd()}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-primary)'
          }}
          style={{
            background: 'var(--bg-card-hover)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '8px 10px',
            color: 'var(--text-base)',
            fontSize: 13,
            width: '100%',
            boxSizing: 'border-box',
            outline: 'none',
          }}
        />
      </label>
    </div>
  )
}

interface ClipCardProps {
  clip: MixClip
  mixId: string
  isSelected: boolean
  onSelect: () => void
  onDelete: () => void
}

function fmt(sec: number) {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatPreciseSeconds(sec: number) {
  return `${sec.toFixed(2)}s`
}

function formatInputSeconds(milliseconds: number) {
  return (milliseconds / 1000).toFixed(2)
}

export default function ClipCard({ clip, mixId, isSelected, onSelect, onDelete }: ClipCardProps) {
  const title = clip.song_detail?.title ?? `Clip #${clip.position + 1}`

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const rafRef = useRef<number>(0)
  const seekingRef = useRef(false)

  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [loadingUrl, setLoadingUrl] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [currentSec, setCurrentSec] = useState(0)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const startSec = clip.start_time_ms / 1000
  const endSec = clip.end_time_ms / 1000
  const clipDuration = Math.max(endSec - startSec, 0.1)
  const progress = clipDuration > 0 ? Math.min((currentSec - startSec) / clipDuration, 1) : 0

  useEffect(() => {
    if (!clip.song_detail?.id) return
    setLoadingUrl(true)
    getSongPlayUrl(clip.song_detail.id)
      .then((url) => {
        setAudioUrl(url)
      })
      .catch(() => setAudioUrl(null))
      .finally(() => setLoadingUrl(false))
  }, [clip.song_detail?.id])

  useEffect(() => {
    return () => {
      cancelAnimationFrame(rafRef.current)
      audioRef.current?.pause()
    }
  }, [])

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = Math.min(clip.volume, 1)
  }, [clip.volume])

  useEffect(() => {
    if (playing && audioRef.current) {
      const t = audioRef.current.currentTime
      if (t < startSec || t >= endSec) audioRef.current.currentTime = startSec
    }
  }, [startSec, endSec, playing])

  const tick = useCallback(() => {
    const audio = audioRef.current
    if (!audio || seekingRef.current) return
    const t = audio.currentTime
    if (t >= endSec) {
      audio.currentTime = startSec
      audio.pause()
      setPlaying(false)
      setCurrentSec(startSec)
      return
    }
    setCurrentSec(t)
    rafRef.current = requestAnimationFrame(tick)
  }, [startSec, endSec])

  function stopPlayback(resetPosition = false) {
    cancelAnimationFrame(rafRef.current)
    audioRef.current?.pause()
    setPlaying(false)
    if (resetPosition) {
      setCurrentSec(startSec)
    }
  }

  async function handlePlay(e: React.MouseEvent) {
    e.stopPropagation()
    if (!audioUrl) return
    if (playing) {
      stopPlayback()
      return
    }

    if (!audioRef.current) audioRef.current = new Audio()
    const audio = audioRef.current

    if (audio.src !== audioUrl) {
      audio.src = audioUrl
    }

    audio.volume = Math.min(clip.volume, 1)
    audio.currentTime = currentSec <= startSec || currentSec >= endSec ? startSec : currentSec

    try {
      await audio.play()
      setPlaying(true)
      rafRef.current = requestAnimationFrame(tick)
    } catch (err) {
      console.error('Error reproduciendo:', err)
    }
  }

  function handleSeek(e: React.MouseEvent<HTMLDivElement>) {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const newTime = startSec + ratio * clipDuration
    setCurrentSec(newTime)
    if (audioRef.current) {
      audioRef.current.currentTime = newTime
    }
  }

  async function confirmDelete() {
    setDeleting(true)
    stopPlayback(true)
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
          onClick={handlePlay}
          disabled={loadingUrl || !audioUrl}
          style={{
            background: 'none',
            border: 'none',
            cursor: loadingUrl || !audioUrl ? 'not-allowed' : 'pointer',
            color: 'var(--text-base)',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            flexShrink: 0,
            opacity: loadingUrl || !audioUrl ? 0.4 : 1,
          }}
        >
          {loadingUrl ? (
            <LoaderCircle size={18} className="animate-spin" aria-hidden="true" />
          ) : playing ? (
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
          onClick={handleSeek}
          style={{
            flex: 1,
            height: 4,
            borderRadius: 2,
            background: 'var(--border-strong)',
            cursor: 'pointer',
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
              transition: playing ? 'none' : 'width 0.1s',
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

        <Volume2
          size={14}
          aria-hidden="true"
          style={{ color: 'var(--text-subdued)', flexShrink: 0 }}
        />
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
