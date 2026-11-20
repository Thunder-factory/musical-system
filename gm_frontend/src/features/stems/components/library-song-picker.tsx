import { useEffect, useState } from 'react'
import { Check, LoaderCircle, Music2, Search } from 'lucide-react'

import { Button, EmptyState, Input } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { getLibrary, type LibrarySong } from '../../songs/api/songs.api'
import { STEM_CREDIT_COST } from '../api/stems.api'

interface LibrarySongPickerProps {
  selectedSongId: string | null
  loading: boolean
  insufficientCredits: boolean
  onSelectSong: (songId: string) => void
  onSubmit: (songId: string, title: string) => void
}

function formatDuration(seconds?: number): string {
  if (!seconds) {
    return '—'
  }
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, '0')}`
}

export default function LibrarySongPicker({
  selectedSongId,
  loading,
  insufficientCredits,
  onSelectSong,
  onSubmit,
}: LibrarySongPickerProps) {
  const [songs, setSongs] = useState<LibrarySong[]>([])
  const [fetching, setFetching] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    let cancelled = false
    setFetching(true)
    setFetchError(false)
    getLibrary('karaoke')
      .then((data) => {
        if (!cancelled) {
          setSongs(data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFetchError(true)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setFetching(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const filtered = songs.filter((song) =>
    song.title?.toLowerCase().includes(search.toLowerCase())
  )
  const selectedSong = songs.find((song) => song.id === selectedSongId) ?? null

  if (fetching) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted">
        <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
        Cargando tu biblioteca...
      </div>
    )
  }

  if (fetchError) {
    return (
      <EmptyState
        icon={<Music2 size={22} aria-hidden="true" />}
        title="No se pudo cargar tu biblioteca"
        description="Intenta recargar o sube un archivo de audio directamente."
      />
    )
  }

  if (songs.length === 0) {
    return (
      <EmptyState
        icon={<Music2 size={22} aria-hidden="true" />}
        title="No tienes canciones listas todavía"
        description="Crea tu primera canción o sube un archivo MP3/WAV en la otra pestaña."
        actionLabel="Crear canción"
        actionTo="/create"
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="relative">
        <Search
          size={15}
          aria-hidden="true"
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
        />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar canción en tu biblioteca..."
          aria-label="Buscar canción en tu biblioteca"
          className="pl-10"
        />
      </div>

      <ul className="flex max-h-64 flex-col gap-2 overflow-y-auto pr-1">
        {filtered.map((song) => {
          const selected = song.id === selectedSongId
          return (
            <li key={song.id}>
              <button
                type="button"
                disabled={loading}
                onClick={() => onSelectSong(song.id)}
                aria-pressed={selected}
                className={cn(
                  'flex w-full items-center justify-between gap-3 rounded-xl border px-3.5 py-2.5 text-left transition-colors disabled:opacity-50',
                  selected
                    ? 'border-primary bg-primary-soft'
                    : 'border-border bg-card-hover hover:border-border-strong'
                )}
              >
                <div className="flex min-w-0 items-center gap-3">
                  {song.thumbnail_url ? (
                    <img
                      src={song.thumbnail_url}
                      alt=""
                      className="h-10 w-10 shrink-0 rounded-lg object-cover"
                    />
                  ) : (
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface text-muted">
                      <Music2 size={16} aria-hidden="true" />
                    </span>
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">
                      {song.title || 'Sin título'}
                    </p>
                    <p className="text-xs text-muted">{formatDuration(song.audio_duration)}</p>
                  </div>
                </div>
                {selected && <Check size={16} className="shrink-0 text-primary" aria-hidden="true" />}
              </button>
            </li>
          )
        })}
      </ul>

      <div className="flex justify-end">
        <Button
          loading={loading}
          disabled={!selectedSong || insufficientCredits || loading}
          costCredits={STEM_CREDIT_COST}
          onClick={() => selectedSong && onSubmit(selectedSong.id, selectedSong.title || 'Canción')}
        >
          {loading ? 'Separando…' : 'Separar pistas'}
        </Button>
      </div>
    </div>
  )
}
