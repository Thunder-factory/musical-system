import { useEffect, useState } from 'react'
import { Heart, LoaderCircle, Music2, Pause, Play } from 'lucide-react'

import { Badge } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { getSongThumbnailUrl } from '../../songs/api/songs.api'
import { recordPlay, toggleLike, type CommunitySong } from '../api/community.api'

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) {
    return 'Ahora'
  }
  if (minutes < 60) {
    return `Hace ${minutes}m`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `Hace ${hours}h`
  }
  return `Hace ${Math.floor(hours / 24)}d`
}

function CommunitySongCard({
  song: initial,
  onPlay,
  isActive,
  isPlaying,
  isLoading,
}: {
  song: CommunitySong
  onPlay: (song: CommunitySong, coverUrl?: string) => void
  isActive: boolean
  isPlaying: boolean
  isLoading: boolean
}) {
  const [song, setSong] = useState(initial)
  const [coverUrl, setCoverUrl] = useState<string | undefined>(undefined)

  useEffect(() => {
    setSong(initial)
  }, [initial])

  useEffect(() => {
    if (!song.thumbnail_s3_key) {
      setCoverUrl(undefined)
      return
    }
    let cancelled = false
    getSongThumbnailUrl(song.id)
      .then((url) => {
        if (!cancelled) {
          setCoverUrl(url)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [song.id, song.thumbnail_s3_key])

  async function handleLike() {
    try {
      const result = await toggleLike(song.id)
      setSong((prev) => ({ ...prev, is_liked: result.liked, like_count: result.like_count }))
    } catch {
      toast.error('No se pudo actualizar tu me gusta')
    }
  }

  const initials = song.user_name
    ? song.user_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : '?'
  const primaryTag = song.tags[0]

  return (
    <article className="overflow-hidden rounded-2xl border border-card-hover bg-card transition-colors hover:border-primary">
      <div className="relative h-60 overflow-hidden bg-card-hover">
        {coverUrl ? (
          <img src={coverUrl} alt={song.title} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-[var(--gradient-primary)] text-black/60">
            <Music2 size={44} aria-hidden="true" />
          </div>
        )}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-night via-transparent to-transparent" />

        {primaryTag && (
          <div className="absolute left-3.5 top-3.5 rounded-full bg-primary px-3 py-1 text-xs font-bold text-black">
            {primaryTag.name}
          </div>
        )}

        <button
          type="button"
          onClick={() => {
            recordPlay(song.id, 0).catch(() => {})
            onPlay(song, coverUrl)
          }}
          aria-label={
            isActive && isPlaying ? `Pausar ${song.title}` : `Reproducir ${song.title}`
          }
          className="absolute bottom-3.5 right-3.5 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-black shadow-[var(--shadow)] transition-transform hover:scale-105 hover:bg-primary-hover"
        >
          {isLoading ? (
            <LoaderCircle size={20} className="animate-spin" aria-hidden="true" />
          ) : isActive && isPlaying ? (
            <Pause size={20} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={20} fill="currentColor" aria-hidden="true" />
          )}
        </button>
      </div>

      <div className="p-4.5 p-5">
        <div className="mb-3 flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--gradient-primary)] text-xs font-bold text-black">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">{song.user_name}</p>
            <p className="text-xs text-muted">{timeAgo(song.created_at)}</p>
          </div>
        </div>

        <h2 className="truncate text-lg font-bold tracking-tight text-white">{song.title}</h2>

        {song.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {song.tags.slice(0, 2).map((t) => (
              <Badge key={t.id} variant="primary">
                {t.name}
              </Badge>
            ))}
            {song.tags.length > 2 && <Badge variant="neutral">+{song.tags.length - 2}</Badge>}
          </div>
        )}

        {song.description && (
          <p className="mt-2.5 line-clamp-2 text-sm leading-relaxed text-muted">
            {song.description}
          </p>
        )}

        <div className="mt-3.5 flex items-center justify-between border-t border-card-hover pt-3 text-xs text-muted">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => void handleLike()}
              aria-pressed={song.is_liked}
              aria-label={song.is_liked ? `Quitar me gusta a ${song.title}` : `Me gusta ${song.title}`}
              className={`flex items-center gap-1.5 transition-colors ${
                song.is_liked ? 'text-error' : 'hover:text-white'
              }`}
            >
              <Heart size={15} fill={song.is_liked ? 'currentColor' : 'none'} aria-hidden="true" />
              <span className="tabular-nums">{song.like_count.toLocaleString()}</span>
            </button>
            <span className="flex items-center gap-1.5 tabular-nums">
              <Play size={13} fill="currentColor" aria-hidden="true" />
              {song.play_count.toLocaleString()}
            </span>
          </div>
          <span>{timeAgo(song.created_at)}</span>
        </div>
      </div>
    </article>
  )
}

interface CommunitySongGridProps {
  songs: CommunitySong[]
  activeTrackId?: string
  isPlaying: boolean
  loadingSongId: string | null
  onPlay: (song: CommunitySong, coverUrl?: string) => void
}

export default function CommunitySongGrid({
  songs,
  activeTrackId,
  isPlaying,
  loadingSongId,
  onPlay,
}: CommunitySongGridProps) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
      {songs.map((song) => (
        <CommunitySongCard
          key={song.id}
          song={song}
          onPlay={onPlay}
          isActive={activeTrackId === `song:${song.id}`}
          isPlaying={activeTrackId === `song:${song.id}` && isPlaying}
          isLoading={loadingSongId === song.id}
        />
      ))}
    </div>
  )
}
