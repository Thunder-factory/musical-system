import type { PlaylistSongItem } from '../../api/modules/playlists.api'
import { LoaderCircle, Pause, Play } from 'lucide-react'
import styles from './playlist-song-row.module.css'

interface Props {
  item: PlaylistSongItem
  index: number
  active: boolean
  playing: boolean
  loading: boolean
  onPlay: () => void
  onRemove: () => void
}

function formatDuration(seconds?: number): string {
  if (!seconds) {
    return '—'
  }
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

export default function PlaylistSongRow({
  item,
  index,
  active,
  playing,
  loading,
  onPlay,
  onRemove,
}: Props) {
  return (
    <div className={`${styles.row} ${active ? styles.active : ''}`}>
      <span className={styles.index}>{index + 1}</span>
      {item.song.thumbnail_url ? (
        <img src={item.song.thumbnail_url} alt="" className={styles.thumbnail} />
      ) : (
        <div className={`${styles.thumbnail} ${styles.placeholder}`} aria-hidden="true">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
          </svg>
        </div>
      )}
      <div className={styles.info}>
        <p className={styles.title}>{item.song.title ?? 'Sin título'}</p>
        {item.song.tags && item.song.tags.length > 0 && (
          <div className={styles.tags}>
            {item.song.tags.slice(0, 2).map((tag) => (
              <span key={tag.name} className={styles.tag}>
                {tag.name}
              </span>
            ))}
          </div>
        )}
      </div>
      <span className={styles.duration}>{formatDuration(item.song.audio_duration)}</span>
      <button
        type="button"
        onClick={onPlay}
        disabled={loading}
        aria-label={
          loading ? 'Cargando audio' : active && playing ? 'Pausar canción' : 'Reproducir canción'
        }
        title={loading ? 'Cargando audio' : active && playing ? 'Pausar' : 'Reproducir'}
        className={`${styles.playButton} ${active ? styles.playButtonActive : ''}`}
      >
        {loading ? (
          <LoaderCircle size={14} aria-hidden="true" className="animate-spin" />
        ) : active && playing ? (
          <Pause size={14} fill="currentColor" aria-hidden="true" />
        ) : (
          <Play size={14} fill="currentColor" aria-hidden="true" />
        )}
      </button>
      <button
        type="button"
        onClick={onRemove}
        aria-label="Quitar de la playlist"
        title="Quitar de la playlist"
        className={styles.removeButton}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
        </svg>
      </button>
    </div>
  )
}
