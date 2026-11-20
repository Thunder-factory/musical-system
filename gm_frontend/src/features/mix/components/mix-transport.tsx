import { Pause, Play, SkipBack, Square } from 'lucide-react'

import { Button } from '../../../components/ui'
import type { PlaybackState } from '../hooks/useMixPlayback'

interface MixTransportProps {
  playbackState: PlaybackState
  positionMs: number
  totalDurationMs: number
  onTogglePlayback: () => void
  onRestart: () => void
  onStop: () => void
  playbackError?: string | null
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
  playbackError,
}: MixTransportProps) {
  const isPlaying = playbackState === 'playing'

  return (
    <div className="mb-2">
      <div
        aria-label="Transporte del mix"
        className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-2"
      >
        <Button
          variant="secondary"
          size="sm"
          leftIcon={
            isPlaying ? (
              <Pause size={13} fill="currentColor" />
            ) : (
              <Play size={13} fill="currentColor" />
            )
          }
          onClick={onTogglePlayback}
        >
          {isPlaying ? 'Pausar' : 'Reproducir'}
        </Button>

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<SkipBack size={13} />}
          onClick={onRestart}
          aria-label="Reproducir desde el inicio"
        >
          Inicio
        </Button>

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Square size={12} fill="currentColor" />}
          onClick={onStop}
          disabled={playbackState === 'idle'}
          aria-label="Detener mix"
        >
          Detener
        </Button>

        <span className="ml-auto text-xs font-medium tabular-nums text-white">
          {formatTime(positionMs)} / {formatTime(totalDurationMs)}
        </span>
      </div>

      {playbackError && (
        <div role="alert" className="mt-1.5 rounded-md bg-error-soft px-2.5 py-1.5 text-xs text-error">
          {playbackError}
        </div>
      )}
    </div>
  )
}
