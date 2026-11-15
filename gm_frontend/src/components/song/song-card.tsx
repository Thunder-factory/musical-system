// ─────────────────────────────────────────────────────────────────────────────
// src/components/song/SongCard.tsx
// Tarjeta estilo Community: imagen grande full-width con título y tags encima
// del overlay, play button blanco flotante, contenido reducido debajo.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useState } from 'react'
import { Pause, Play } from 'lucide-react'
import { getSongThumbnailUrl } from '../../api/modules/songs.api'
import type { LibrarySong, SongTag } from '../../api/modules/songs.api'
import styles from './song-card.module.css'

interface SongCardProps {
  song: LibrarySong
  onPlay?: (song: LibrarySong) => void
  onLike?: (songId: string) => void
  onDelete?: (songId: string) => void
  onPublish?: (songId: string, isPublic: boolean) => void
  onDownload?: (songId: string) => void
  isActive?: boolean
  isPlaying?: boolean
}

function formatDuration(seconds?: number): string {
  if (!seconds) {
    return '—'
  }
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function CoverPlaceholder() {
  return (
    <div className={styles.coverPlaceholder} aria-hidden="true">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
      </svg>
    </div>
  )
}

export default function SongCard({
  song,
  onPlay,
  onLike,
  onDelete,
  onPublish,
  onDownload,
  isActive = false,
  isPlaying = false,
}: SongCardProps) {
  const [liked, setLiked] = useState(false)
  const [showMenu, setShowMenu] = useState(false)

  type CoverState = 'loading' | 'loaded' | 'error'
  const [coverState, setCoverState] = useState<CoverState>('loading')
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null)

  useEffect(() => {
    if (song.thumbnail_url) {
      setThumbnailUrl(song.thumbnail_url)
      setCoverState('loaded')
      return
    }
    if (!song.thumbnail_s3_key) {
      setThumbnailUrl(null)
      setCoverState('error')
      return
    }
    let cancelled = false
    async function fetchThumbnail() {
      try {
        const url = await getSongThumbnailUrl(song.id)
        if (!cancelled) {
          setThumbnailUrl(url)
          setCoverState('loaded')
        }
      } catch {
        if (!cancelled) {
          setCoverState('error')
        }
      }
    }
    fetchThumbnail()
    return () => {
      cancelled = true
    }
  }, [song.id, song.thumbnail_url, song.thumbnail_s3_key])

  function handleLike() {
    setLiked((prev) => !prev)
    onLike?.(song.id)
  }

  // Tags: prioriza song.tags del backend, cae a genre/mood como fallback
  const tags: string[] =
    song.tags && song.tags.length > 0
      ? song.tags.map((t: SongTag) => t.name)
      : ([song.genre, song.mood].filter(Boolean) as string[])

  return (
    <article className={`${styles.card} ${isActive ? styles.cardActive : ''}`}>
      {/* ── Cover: imagen grande con overlay y metadatos encima ── */}
      <div className={styles.coverWrapper}>
        {coverState === 'loading' && (
          <div className={styles.coverSkeleton} aria-label="Cargando portada..." />
        )}

        {coverState === 'loaded' && thumbnailUrl && (
          <img
            src={thumbnailUrl}
            alt={`Portada de ${song.title ?? 'canción'}`}
            className={styles.cover}
            onError={() => setCoverState('error')}
          />
        )}

        {coverState === 'error' && <CoverPlaceholder />}

        {/* Degradado oscuro permanente en la parte inferior */}
        <div className={styles.coverOverlay} />

        <button
          className={`${styles.likeBtn} ${liked ? styles.liked : ''}`}
          onClick={handleLike}
          aria-label={liked ? 'Quitar like' : 'Dar like'}
          aria-pressed={liked}
          title={liked ? 'Quitar like' : 'Dar like'}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill={liked ? 'currentColor' : 'none'}
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
        </button>

        {/* Título + tags sobre el gradiente */}
        <div className={styles.coverMeta}>
          <h3 className={styles.coverTitle}>{song.title || 'Sin título'}</h3>
          {tags.length > 0 && (
            <div className={styles.coverTagRow}>
              {tags.slice(0, 2).map((tag) => (
                <span key={tag} className={styles.coverTagBadge}>
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Play blanco — aparece en hover */}
        <button
          className={styles.playBtn}
          onClick={() => onPlay?.(song)}
          aria-label={`Reproducir ${song.title}`}
        >
          {isPlaying ? (
            <Pause size={22} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={22} fill="currentColor" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* ── Contenido debajo: fecha, descripción, acciones ─────── */}
      <div className={styles.content}>
        <div className={styles.subRow}>
          <span className={styles.date}>{formatDate(song.created_at)}</span>
          <span className={styles.duration}>{formatDuration(song.audio_duration)}</span>
        </div>

        {song.description && <p className={styles.description}>{song.description}</p>}

        <div className={styles.actions}>
          {onDownload && (
            <button
              className={styles.actionBtn}
              onClick={() => onDownload(song.id)}
              aria-label="Descargar canción"
              title="Descargar"
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z" />
              </svg>
            </button>
          )}

          {onPublish && (
            <button
              className={`${styles.actionBtn} ${styles.publishAction} ${song.is_public ? styles.publishActive : ''}`}
              onClick={() => onPublish(song.id, !song.is_public)}
              aria-label={song.is_public ? 'Despublicar canción' : 'Publicar canción'}
              title={song.is_public ? 'Despublicar' : 'Publicar'}
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M12 5c-5 0-9 7-9 7s4 7 9 7 9-7 9-7-4-7-9-7zm0 12c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" />
              </svg>
              <span>{song.is_public ? 'Publicada' : 'Publicar'}</span>
            </button>
          )}

          {onDelete && (
            <div className={styles.menuWrapper}>
              <button
                className={styles.actionBtn}
                onClick={() => setShowMenu((value) => !value)}
                aria-label="Más acciones"
                aria-expanded={showMenu}
                title="Más acciones"
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <circle cx="5" cy="12" r="2" />
                  <circle cx="12" cy="12" r="2" />
                  <circle cx="19" cy="12" r="2" />
                </svg>
              </button>
              {showMenu && (
                <div className={styles.actionMenu}>
                  <button
                    type="button"
                    onClick={() => {
                      setShowMenu(false)
                      if (
                        window.confirm(
                          `¿Eliminar "${song.title}"? Esta acción no se puede deshacer.`
                        )
                      ) {
                        onDelete(song.id)
                      }
                    }}
                  >
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      aria-hidden="true"
                    >
                      <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
                    </svg>
                    Eliminar
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </article>
  )
}
