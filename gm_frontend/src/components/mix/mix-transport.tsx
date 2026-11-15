import { Pause, Play, SkipBack, Square } from 'lucide-react'
import type { PlaybackState } from '../../hooks/useMixPlayback'

interface MixTransportProps {
  playbackState: PlaybackState
  positionMs: number
  totalDurationMs: number
  onTogglePlayback: () => void
  onRestart: () => void
  onStop: () => void
}

function formatTime(milliseconds: number) {
  const totalSeconds = Math.max(0, milliseconds) / 1000
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = Math.floor(totalSeconds % 60)
  const centiseconds = Math.floor((totalSeconds % 1) * 100)
  return `${minutes}:${String(seconds).padStart(2, '0')}.${String(centiseconds).padStart(2, '0')}`
}

export default function MixTransport({
  playbackState,
  positionMs,
  totalDurationMs,
  onTogglePlayback,
  onRestart,
  onStop,
}: MixTransportProps) {
  const isPlaying = playbackState === 'playing'
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 10px',
        border: '1px solid var(--border)',
        borderRadius: 8,
        background: 'var(--bg-surface)',
      }}
      aria-label="Transporte del mix"
    >
      <button type="button" onClick={onTogglePlayback} style={transportButtonStyle(true)}>
        {isPlaying ? (
          <Pause size={14} fill="currentColor" aria-hidden="true" />
        ) : (
          <Play size={14} fill="currentColor" aria-hidden="true" />
        )}
        <span>{isPlaying ? 'Pausar' : 'Reproducir'}</span>
      </button>
      <button
        type="button"
        onClick={onRestart}
        aria-label="Reproducir desde el inicio"
        title="Reproducir desde el inicio"
        style={transportButtonStyle(true)}
      >
        <SkipBack size={13} aria-hidden="true" />
        <span>Inicio</span>
      </button>
      <button
        type="button"
        onClick={onStop}
        disabled={playbackState === 'idle'}
        aria-label="Detener mix"
        title="Detener"
        style={transportButtonStyle(playbackState !== 'idle')}
      >
        <Square size={13} fill="currentColor" aria-hidden="true" />
        <span>Detener</span>
      </button>
      <span
        style={{
          marginLeft: 'auto',
          color: 'var(--text-base)',
          fontSize: 12,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {formatTime(positionMs)} / {formatTime(totalDurationMs)}
      </span>
    </div>
  )
}

function transportButtonStyle(enabled: boolean) {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '6px 9px',
    border: '1px solid var(--border)',
    borderRadius: 6,
    background: enabled ? 'var(--bg-card-hover)' : 'transparent',
    color: enabled ? 'var(--text-base)' : 'var(--text-subdued)',
    cursor: enabled ? 'pointer' : 'not-allowed',
    fontSize: 12,
    fontWeight: 700,
    opacity: enabled ? 1 : 0.5,
  }
}
