import { useEffect, useState } from 'react'
import { LoaderCircle, Music2, Pause, Play } from 'lucide-react'

import { getSongThumbnailUrl } from '../api/songs.api'

export interface HomeSong {
  id: string
  title: string
  subtitle: string
  tags: string[]
  thumbnailUrl?: string | null
  thumbnailKey?: string | null
}

interface HomeSongCardProps {
  song: HomeSong
  onPlay: (song: HomeSong) => void
  isPlaying: boolean
  isLoading: boolean
}

function useCover(song: HomeSong) {
  const [url, setUrl] = useState<string | null>(song.thumbnailUrl ?? null)

  useEffect(() => {
    if (song.thumbnailUrl) {
      setUrl(song.thumbnailUrl)
      return
    }
    if (!song.thumbnailKey) {
      setUrl(null)
      return
    }
    let cancelled = false
    getSongThumbnailUrl(song.id)
      .then((value) => {
        if (!cancelled) {
          setUrl(value)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [song.id, song.thumbnailUrl, song.thumbnailKey])

  return url
}

export function HomeSongCard({ song, onPlay, isPlaying, isLoading }: HomeSongCardProps) {
  const cover = useCover(song)

  return (
    <div className="group relative w-[200px] shrink-0 overflow-hidden rounded-2xl border border-card-hover bg-card transition-colors hover:border-primary">
      <div className="relative h-[200px] w-full overflow-hidden bg-card-hover">
        {cover ? (
          <img
            src={cover}
            alt={`Portada de ${song.title}`}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="grid h-full w-full place-items-center text-muted" aria-hidden="true">
            <Music2 size={40} />
          </div>
        )}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to top, color-mix(in srgb, var(--bg-base) 75%, transparent) 0%, transparent 45%)',
          }}
        />

        <button
          type="button"
          onClick={() => onPlay(song)}
          disabled={isLoading}
          aria-label={isPlaying ? `Pausar ${song.title}` : `Reproducir ${song.title}`}
          className="absolute bottom-3 right-3 grid h-10 w-10 place-items-center rounded-full bg-primary text-black transition-transform hover:scale-105 disabled:opacity-60"
        >
          {isLoading ? (
            <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
          ) : isPlaying ? (
            <Pause size={16} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={16} fill="currentColor" className="ml-0.5" aria-hidden="true" />
          )}
        </button>
      </div>

      <div className="space-y-1.5 p-3">
        <p className="truncate text-sm font-semibold text-white">{song.title}</p>
        <p className="truncate text-xs text-muted">{song.subtitle}</p>
        {song.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {song.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-card-hover px-2 py-0.5 text-[10px] text-muted"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default HomeSongCard
