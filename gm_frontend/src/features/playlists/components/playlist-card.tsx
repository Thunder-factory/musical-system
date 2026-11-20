import { ListMusic } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '../../../components/ui'
import { getPlaylistCoverUrl, type Playlist } from '../api/playlists.api'

interface PlaylistCardProps {
  playlist: Playlist
}

export default function PlaylistCard({ playlist }: PlaylistCardProps) {
  const isAuto = playlist.type !== 'manual'
  const coverUrl = getPlaylistCoverUrl(playlist)

  return (
    <Link
      to={`/playlists/${playlist.id}`}
      className="group flex flex-col rounded-xl border border-border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-border-strong hover:bg-card-hover"
    >
      <div className="mb-3 aspect-square w-full overflow-hidden rounded-lg bg-card-hover">
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={playlist.title}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted">
            <ListMusic size={36} aria-hidden="true" />
          </div>
        )}
      </div>

      <p className="truncate text-sm font-semibold text-white">{playlist.title}</p>
      <p className="mt-0.5 text-xs text-muted">
        {playlist.song_count} canción{playlist.song_count !== 1 ? 'es' : ''}
      </p>

      <div className="mt-2.5">
        <Badge variant={isAuto ? 'success' : 'primary'}>
          {isAuto ? 'Automática' : 'Manual'}
        </Badge>
      </div>
    </Link>
  )
}
