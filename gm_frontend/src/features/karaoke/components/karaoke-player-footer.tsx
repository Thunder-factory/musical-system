import { Pause, Play, RotateCcw, RotateCw } from 'lucide-react'

function formatTime(s: number): string {
  if (!Number.isFinite(s) || s < 0) {
    return '0:00'
  }
  const m = Math.floor(s / 60)
  return `${m}:${Math.floor(s % 60).toString().padStart(2, '0')}`
}

interface KaraokePlayerFooterProps {
  songTitle: string
  isPlaying: boolean
  currentTime: number
  duration: number
  onTogglePlay: () => void
  onSkip: (seconds: number) => void
  onSeek: (time: number) => void
}

export default function KaraokePlayerFooter({
  songTitle,
  isPlaying,
  currentTime,
  duration,
  onTogglePlay,
  onSkip,
  onSeek,
}: KaraokePlayerFooterProps) {
  return (
    <footer className="z-10 flex shrink-0 flex-col gap-2.5 px-8 pb-5 pt-3">
      <div className="flex items-center justify-between gap-3">
        <span className="max-w-[70%] truncate text-sm font-bold text-white">{songTitle}</span>
        <span className="shrink-0 text-xs tabular-nums text-muted">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>

      <input
        type="range"
        min={0}
        max={duration > 0 ? duration : 100}
        step={0.1}
        value={Math.min(currentTime, duration || 100)}
        disabled={duration <= 0}
        aria-label="Progreso de reproducción"
        onChange={(e) => onSeek(Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer accent-primary"
      />

      <div className="flex items-center justify-center gap-5">
        <button
          type="button"
          onClick={() => onSkip(-10)}
          aria-label="Retroceder 10 segundos"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-card-hover text-white/80 transition-colors hover:bg-border-strong hover:text-white"
        >
          <RotateCcw size={16} aria-hidden="true" />
        </button>

        <button
          type="button"
          onClick={onTogglePlay}
          aria-label={isPlaying ? 'Pausar' : 'Reproducir'}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-black transition-transform hover:scale-105 hover:bg-primary-hover"
        >
          {isPlaying ? (
            <Pause size={20} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={20} fill="currentColor" aria-hidden="true" />
          )}
        </button>

        <button
          type="button"
          onClick={() => onSkip(10)}
          aria-label="Adelantar 10 segundos"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-card-hover text-white/80 transition-colors hover:bg-border-strong hover:text-white"
        >
          <RotateCw size={16} aria-hidden="true" />
        </button>
      </div>
    </footer>
  )
}
