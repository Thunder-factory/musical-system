import { Pause, Play } from 'lucide-react'

import { formatClipDuration } from '../types/faceswap.types'

interface Props {
  playing: boolean
  time: number
  duration: number
  onToggle: () => void
  onSeek: (seconds: number) => void
  disabled?: boolean
}

export default function FaceTargetControls({
  playing,
  time,
  duration,
  onToggle,
  onSeek,
  disabled = false,
}: Props) {
  const max = duration > 0 ? duration : 0
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onToggle}
        disabled={disabled || max === 0}
        aria-label={playing ? 'Pausar video' : 'Reproducir video'}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-card-hover text-white transition-colors hover:text-primary disabled:opacity-50"
      >
        {playing ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
      </button>
      <input
        type="range"
        min={0}
        max={max}
        step={0.04}
        value={Math.min(time, max)}
        disabled={disabled || max === 0}
        onChange={(e) => onSeek(Number(e.target.value))}
        aria-label="Momento del video"
        aria-valuetext={`${formatClipDuration(time)} de ${formatClipDuration(max)}`}
        className="h-1.5 min-w-0 flex-1 cursor-pointer accent-[var(--color-primary)] disabled:cursor-not-allowed"
      />
      <span className="shrink-0 text-xs tabular-nums text-muted" aria-live="off">
        {formatClipDuration(time)} / {formatClipDuration(max)}
      </span>
    </div>
  )
}
