import type { RefObject } from 'react'
import { Music2 } from 'lucide-react'

interface KaraokePlayerFooterProps {
  audioRef: RefObject<HTMLAudioElement | null>
  audioUrl: string | null
  songTitle: string
  subtitle?: string
  onTimeUpdate?: (currentTime: number) => void
  onDurationChange?: (duration: number) => void
  onPlayingChange?: (playing: boolean) => void
}

/**
 * Barra del karaoke individual con los controles nativos del navegador (los mismos del
 * reproductor general: volumen, velocidad, descarga). Usa el mismo audioRef que la letra,
 * así que la sincronización no cambia.
 */
export default function KaraokePlayerFooter({
  audioRef,
  audioUrl,
  songTitle,
  subtitle = 'Karaoke · instrumental',
  onTimeUpdate,
  onDurationChange,
  onPlayingChange,
}: KaraokePlayerFooterProps) {
  return (
    <footer className="z-10 shrink-0 px-3 pb-3 pt-2 sm:px-6 sm:pb-4">
      <div className="flex min-h-[72px] flex-wrap items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 shadow-lg sm:flex-nowrap sm:gap-4 sm:px-6">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-card-hover text-muted"
          aria-hidden="true"
        >
          <Music2 size={18} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col sm:max-w-[220px] sm:flex-none">
          <span className="truncate text-sm font-semibold text-white">{songTitle}</span>
          <span className="truncate text-xs text-muted">{subtitle}</span>
        </div>
        {audioUrl ? (
          <audio
            ref={audioRef}
            src={audioUrl}
            controls
            className="h-9 w-full min-w-0 flex-1 accent-primary [color-scheme:dark] sm:w-auto"
            onTimeUpdate={(event) => onTimeUpdate?.(event.currentTarget.currentTime)}
            onDurationChange={(event) => onDurationChange?.(event.currentTarget.duration)}
            onPlay={() => onPlayingChange?.(true)}
            onPause={() => onPlayingChange?.(false)}
            onEnded={() => onPlayingChange?.(false)}
          />
        ) : (
          <span className="text-xs text-muted">Cargando audio...</span>
        )}
      </div>
    </footer>
  )
}
