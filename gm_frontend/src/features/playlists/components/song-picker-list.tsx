import { Check } from 'lucide-react'

import type { LibrarySong } from '../../songs/api/songs.api'

interface SongPickerListProps {
  songs: LibrarySong[]
  loading: boolean
  selectedIds: Set<string>
  onToggle: (id: string) => void
}

export default function SongPickerList({
  songs,
  loading,
  selectedIds,
  onToggle,
}: SongPickerListProps) {
  if (loading) {
    return <p className="py-8 text-center text-sm text-muted">Cargando canciones...</p>
  }
  if (songs.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted">
        No tienes canciones en tu biblioteca todavía.
      </p>
    )
  }

  return (
    <div className="max-h-72 space-y-1 overflow-y-auto pr-1">
      {songs.map((song) => {
        const selected = selectedIds.has(song.id)
        return (
          <button
            key={song.id}
            type="button"
            onClick={() => onToggle(song.id)}
            aria-pressed={selected}
            className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition-colors ${
              selected ? 'border-primary bg-primary-soft' : 'border-transparent hover:bg-card-hover'
            }`}
          >
            <span
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                selected
                  ? 'border-primary bg-primary text-black'
                  : 'border-border-strong bg-transparent'
              }`}
            >
              {selected && <Check size={12} strokeWidth={3} aria-hidden="true" />}
            </span>
            <div className="min-w-0 flex-1">
              <p
                className={`truncate text-sm font-medium ${selected ? 'text-primary' : 'text-white'}`}
              >
                {song.title || 'Sin título'}
              </p>
              {song.tags && song.tags.length > 0 && (
                <p className="truncate text-xs text-muted">
                  {song.tags.map((t) => t.name).join(', ')}
                </p>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}
