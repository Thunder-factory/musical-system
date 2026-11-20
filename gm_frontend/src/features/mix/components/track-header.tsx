import { Pause, Play, Volume2, VolumeX } from 'lucide-react'

import type { MixClip } from '../api/mix.api'
import styles from './clip-timeline.module.css'

interface TrackHeaderProps {
  clip: MixClip
  index: number
  color: string
  isSelected: boolean
  isPlaying: boolean
  muted: boolean
  solo: boolean
  onSelect: () => void
  onTogglePlay: () => void
  onToggleMute: () => void
  onToggleSolo: () => void
}

export default function TrackHeader({
  clip,
  index,
  color,
  isSelected,
  isPlaying,
  muted,
  solo,
  onSelect,
  onTogglePlay,
  onToggleMute,
  onToggleSolo,
}: TrackHeaderProps) {
  const title = clip.custom_audio_name ?? clip.song_detail?.title ?? `Clip #${clip.position + 1}`
  const sourceLabel = clip.is_external
    ? 'Archivo externo'
    : (clip.song_detail?.genre ?? 'Audio')

  return (
    <div
      className={`${styles.trackHeader} ${isSelected ? styles.trackHeaderSelected : ''}`}
      style={{ '--track-color': color } as React.CSSProperties}
    >
      <button
        type="button"
        className={styles.trackPlay}
        onClick={onTogglePlay}
        aria-label={isPlaying ? `Pausar ${title}` : `Reproducir ${title}`}
        title={isPlaying ? 'Pausar pista' : 'Reproducir pista'}
      >
        {isPlaying ? (
          <Pause size={12} fill="currentColor" aria-hidden="true" />
        ) : (
          <Play size={12} fill="currentColor" aria-hidden="true" />
        )}
      </button>
      <button
        type="button"
        className={styles.trackIdentity}
        onClick={onSelect}
        aria-pressed={isSelected}
        title={`Seleccionar ${title}`}
      >
        <span className={styles.trackColor} aria-hidden="true" />
        <span className={styles.trackText}>
          <strong>
            {index + 1}. {title}
          </strong>
          <small>{sourceLabel}</small>
        </span>
      </button>
      <div className={styles.trackControls}>
        <button
          type="button"
          className={`${styles.controlButton} ${muted ? styles.controlButtonActive : ''}`}
          onClick={onToggleMute}
          aria-pressed={muted}
          aria-label={muted ? `Activar ${title}` : `Silenciar ${title}`}
          title={muted ? 'Activar sonido' : 'Silenciar canal'}
        >
          {muted ? (
            <VolumeX size={11} aria-hidden="true" />
          ) : (
            <Volume2 size={11} aria-hidden="true" />
          )}
          <span>M</span>
        </button>
        <button
          type="button"
          className={`${styles.controlButton} ${solo ? styles.controlButtonActive : ''}`}
          onClick={onToggleSolo}
          aria-pressed={solo}
          aria-label={`${solo ? 'Desactivar' : 'Activar'} solo de ${title}`}
          title="Solo"
        >
          S
        </button>
      </div>
    </div>
  )
}
