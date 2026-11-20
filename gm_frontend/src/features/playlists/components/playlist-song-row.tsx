import { LoaderCircle, Music2, Pause, Play, X } from 'lucide-react'

import { Badge } from '../../../components/ui'
import type { PlaylistSongItem } from '../api/playlists.api'

interface PlaylistSongRowProps {
  item: PlaylistSongItem
  index: number
  active: boolean
  playing: boolean
  loading: boolean
  onPlay: () => void
  onRemove?: () => void
}

function formatDuration(seconds?: number): string {
  if (!seconds) {
    return '—'
  }
  const minutes = Math.floor(seconds / 60)
  const remaining = Math.floor(seconds % 60)
  return `${minutes}:${remaining.toString().padStart(2, '0')}`
}

export default function PlaylistSongRow({
  item,
  index,
  active,
  playing,
  loading,
  onPlay,
  onRemove,
}: PlaylistSongRowProps) {
  return (
    <div
      className={`flex min-h-[54px] items-center gap-3 rounded-lg px-3 py-2 transition-colors ${
        active ? 'bg-primary-soft' : 'hover:bg-card-hover'
      }`}
    >
      <span className="w-6 shrink-0 text-center text-xs tabular-nums text-muted">{index + 1}</span>

      {item.song.thumbnail_url ? (
        <img
          src={item.song.thumbnail_url}
          alt=""
          className="h-9 w-9 shrink-0 rounded-md bg-card-hover object-cover"
        />
      ) : (
        <div
          aria-hidden="true"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-card-hover text-muted"
        >
          <Music2 size={16} />
        </div>
      )}

      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm font-medium ${active ? 'text-primary' : 'text-white'}`}>
          {item.song.title ?? 'Sin título'}
        </p>
        {item.song.tags && item.song.tags.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {item.song.tags.slice(0, 2).map((tag) => (
              <Badge key={tag.name} variant="neutral">
                {tag.name}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <span className="shrink-0 text-xs tabular-nums text-muted">
        {formatDuration(item.song.audio_duration)}
      </span>

      <button
        type="button"
        onClick={onPlay}
        disabled={loading}
        aria-label={
          loading ? 'Cargando audio' : active && playing ? 'Pausar canción' : 'Reproducir canción'
        }
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors ${
          active ? 'bg-primary text-black' : 'bg-card-hover text-white hover:bg-border-strong'
        }`}
      >
        {loading ? (
          <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
        ) : active && playing ? (
          <Pause size={14} fill="currentColor" aria-hidden="true" />
        ) : (
          <Play size={14} fill="currentColor" aria-hidden="true" />
        )}
      </button>

      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Quitar ${item.song.title ?? 'canción'} de la playlist`}
          title="Quitar de la playlist"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-error-soft hover:text-error"
        >
          <X size={14} aria-hidden="true" />
        </button>
      )}
    </div>
  )
}
