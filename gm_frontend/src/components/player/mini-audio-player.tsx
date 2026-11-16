import type { RefObject } from 'react'
import { FileText, Music2, X } from 'lucide-react'
import styles from './mini-audio-player.module.css'

interface MiniAudioPlayerProps {
  audioRef: RefObject<HTMLAudioElement | null>
  audioUrl: string | null
  title: string
  subtitle?: string
  coverUrl?: string | null
  loading?: boolean
  showLyrics?: boolean
  onToggleLyrics?: () => void
  onPlay?: () => void
  onPause?: () => void
  onEnded?: () => void
  onClose?: () => void
  onTimeUpdate?: (currentTime: number) => void
  onLoadedMetadata?: (duration: number) => void
}

export default function MiniAudioPlayer({
  audioRef,
  audioUrl,
  title,
  subtitle,
  coverUrl,
  loading = false,
  showLyrics = false,
  onToggleLyrics,
  onPlay,
  onPause,
  onEnded,
  onClose,
  onTimeUpdate,
  onLoadedMetadata,
}: MiniAudioPlayerProps) {
  return (
    <div className={styles.miniPlayer}>
      {loading ? (
        <span className={styles.loading}>Cargando audio...</span>
      ) : audioUrl ? (
        <>
          <div className={styles.cover} aria-hidden="true">
            {coverUrl ? <img src={coverUrl} alt="" /> : <Music2 size={18} />}
          </div>
          <div className={styles.info}>
            <span className={styles.title}>{title}</span>
            {subtitle && <span className={styles.subtitle}>{subtitle}</span>}
          </div>
          <audio
            ref={audioRef}
            key={audioUrl}
            src={audioUrl}
            controls
            autoPlay
            onPlay={onPlay}
            onPause={onPause}
            onEnded={onEnded}
            onTimeUpdate={(event) => onTimeUpdate?.(event.currentTarget.currentTime)}
            onLoadedMetadata={(event) => onLoadedMetadata?.(event.currentTarget.duration)}
            className={styles.audio}
          />
          {onToggleLyrics && (
            <button
              type="button"
              onClick={onToggleLyrics}
              className={`${styles.lyricsButton} ${showLyrics ? styles.lyricsButtonActive : ''}`}
              aria-label={showLyrics ? 'Cerrar letra' : 'Ver letra'}
              title={showLyrics ? 'Cerrar letra' : 'Ver letra'}
            >
              <FileText size={16} aria-hidden="true" />
            </button>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className={styles.closeButton}
              aria-label="Cerrar reproductor"
              title="Cerrar reproductor"
            >
              <X size={16} aria-hidden="true" />
            </button>
          )}
        </>
      ) : null}
    </div>
  )
}
