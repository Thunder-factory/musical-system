import { Heart, LoaderCircle, Music2, Pause, Play } from 'lucide-react'

import { cn } from '../../../lib/cn'
import type { LibrarySong } from '../api/songs.api'
import { useSongCover } from './song-card-helpers'

interface SongCardCoverProps {
  song: LibrarySong
  tags: string[]
  liked: boolean
  likes: number
  liking: boolean
  isPlaying: boolean
  isLoading: boolean
  onPlay: () => void
  onLike: () => void
}

export function SongCardCover({
  song,
  tags,
  liked,
  likes,
  liking,
  isPlaying,
  isLoading,
  onPlay,
  onLike,
}: SongCardCoverProps) {
  const { thumbnailUrl, setThumbnailUrl, coverLoading } = useSongCover(song)

  return (
    <div className="relative h-[210px] overflow-hidden rounded-t-2xl bg-card-hover">
      {coverLoading ? (
        <div className="h-full w-full animate-pulse bg-card-hover" aria-label="Cargando portada..." />
      ) : thumbnailUrl ? (
        <img
          src={thumbnailUrl}
          alt={`Portada de ${song.title ?? 'canción'}`}
          onError={() => setThumbnailUrl(null)}
          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-muted" aria-hidden="true">
          <Music2 size={40} />
        </div>
      )}

      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'linear-gradient(to top, color-mix(in srgb, var(--bg-base) 88%, transparent) 0%, color-mix(in srgb, var(--bg-base) 25%, transparent) 55%, transparent 100%)',
        }}
      />

      <button
        type="button"
        onClick={onLike}
        disabled={liking}
        aria-label={liked ? 'Quitar me gusta' : 'Dar me gusta'}
        aria-pressed={liked}
        className={cn(
          'absolute right-3 top-3 z-10 inline-flex h-8 items-center gap-1 rounded-full border px-2.5 text-xs font-semibold backdrop-blur-sm transition-colors',
          liked
            ? 'border-error-border bg-night/70 text-error'
            : 'border-white/20 bg-night/55 text-white hover:bg-night/80'
        )}
      >
        <Heart size={14} fill={liked ? 'currentColor' : 'none'} aria-hidden="true" />
        {likes > 0 && <span className="tabular-nums">{likes}</span>}
      </button>

      <div className="absolute bottom-0 left-0 right-14 flex flex-col gap-1.5 p-3.5">
        <h3 className="truncate text-base font-bold leading-snug text-white">
          {song.title || 'Sin título'}
        </h3>
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {tags.slice(0, 2).map((tag) => (
              <span
                key={tag}
                className="rounded-full border border-white/15 bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white/90"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={onPlay}
        disabled={isLoading}
        aria-busy={isLoading}
        aria-label={isPlaying ? `Pausar ${song.title}` : `Reproducir ${song.title}`}
        className="absolute bottom-3 right-3 flex h-11 w-11 items-center justify-center rounded-full bg-primary text-black shadow-[var(--shadow)] transition-transform hover:scale-105 disabled:opacity-60"
      >
        {isLoading ? (
          <LoaderCircle size={18} className="animate-spin" aria-hidden="true" />
        ) : isPlaying ? (
          <Pause size={18} fill="currentColor" aria-hidden="true" />
        ) : (
          <Play size={18} fill="currentColor" className="ml-0.5" aria-hidden="true" />
        )}
      </button>
    </div>
  )
}
