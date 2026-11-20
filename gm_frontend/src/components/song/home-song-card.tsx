// Tarjeta compacta para las filas horizontales de Inicio (tendencias y "para ti").
import { useEffect, useState } from 'react'
import { LoaderCircle, Music2, Pause, Play } from 'lucide-react'
import { getSongThumbnailUrl } from '../../api/modules/songs.api'

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
    if (song.thumbnailUrl || !song.thumbnailKey) {
      return
    }
    let cancelled = false
    getSongThumbnailUrl(song.id)
      .then((value) => !cancelled && setUrl(value))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [song.id, song.thumbnailUrl, song.thumbnailKey])

  return url
}

export default function HomeSongCard({ song, onPlay, isPlaying, isLoading }: HomeSongCardProps) {
  const cover = useCover(song)

  return (
    <div className="group relative shrink-0 w-[200px] rounded-2xl overflow-hidden bg-card border border-card-hover hover:border-primary transition-colors">
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
          className="absolute bottom-3 right-3 grid place-items-center h-10 w-10 rounded-full bg-primary text-black transition-transform hover:scale-105"
        >
          {isLoading ? (
            <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
          ) : isPlaying ? (
            <Pause size={16} fill="black" aria-hidden="true" />
          ) : (
            <Play size={16} fill="black" className="ml-0.5" aria-hidden="true" />
          )}
        </button>
      </div>

      <div className="p-3 space-y-2">
        <p className="text-sm font-semibold text-white truncate">{song.title}</p>
        <p className="text-xs text-muted truncate">{song.subtitle}</p>
        {song.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {song.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="text-[10px] px-2 py-0.5 rounded-full bg-card-hover text-muted"
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
