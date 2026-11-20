import { Music2, Plus } from 'lucide-react'

import { EmptyState } from '../../../components/ui'
import type { LibrarySong } from '../../songs/api/songs.api'

interface LibraryClipTabProps {
  songs: LibrarySong[]
  adding: boolean
  onSelectSong: (song: LibrarySong) => void
}

export default function LibraryClipTab({ songs, adding, onSelectSong }: LibraryClipTabProps) {
  if (songs.length === 0) {
    return (
      <div className="p-4">
        <EmptyState
          icon={<Music2 size={22} />}
          title="Sin canciones en tu biblioteca"
          description="Crea o sube canciones para poder añadirlas a tu línea de tiempo."
          actionLabel="Crear canción"
          actionTo="/create"
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col py-1">
      {songs.map((song) => (
        <button
          key={song.id}
          type="button"
          onClick={() => !adding && onSelectSong(song)}
          disabled={adding}
          className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-card-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-card-hover text-primary">
            <Music2 size={16} aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{song.title}</p>
            <p className="truncate text-xs text-muted">
              {song.tags?.slice(0, 3).map((t) => t.name).join(', ') || 'Sin etiquetas'}
            </p>
          </div>
          <Plus size={15} className="shrink-0 text-muted" aria-hidden="true" />
        </button>
      ))}
    </div>
  )
}
