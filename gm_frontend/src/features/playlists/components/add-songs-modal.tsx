import { useEffect, useState } from 'react'
import { Check, Music2, Search } from 'lucide-react'

import { Button, Input, Modal } from '../../../components/ui'
import { getLibrary, type LibrarySong } from '../../songs/api/songs.api'
import { addSongToPlaylist } from '../api/playlists.api'

interface AddSongsModalProps {
  open: boolean
  playlistId: string
  existingSongIds: Set<string>
  onClose: () => void
  onAdded: () => Promise<void>
}

export default function AddSongsModal({
  open,
  playlistId,
  existingSongIds,
  onClose,
  onAdded,
}: AddSongsModalProps) {
  const [library, setLibrary] = useState<LibrarySong[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      return
    }
    setSelectedIds(new Set())
    setSearch('')
    setError(null)
    setLoading(true)
    getLibrary()
      .then(setLibrary)
      .catch(() => setError('No se pudo cargar tu biblioteca.'))
      .finally(() => setLoading(false))
  }, [open])

  function toggle(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  async function handleConfirm() {
    if (selectedIds.size === 0 || adding) {
      return
    }
    setAdding(true)
    setError(null)
    const failed: string[] = []
    try {
      for (const songId of selectedIds) {
        try {
          await addSongToPlaylist(playlistId, songId)
        } catch {
          failed.push(songId)
        }
      }
      if (failed.length > 0) {
        setError(
          failed.length === selectedIds.size
            ? 'No se pudo agregar ninguna canción.'
            : `No se pudieron agregar ${failed.length} canciones.`
        )
        return
      }
      await onAdded()
      onClose()
    } catch {
      setError('No se pudo actualizar la playlist.')
    } finally {
      setAdding(false)
    }
  }

  const query = search.trim().toLowerCase()
  const available = library
    .filter((s) => !existingSongIds.has(s.id))
    .filter((s) => !query || s.title.toLowerCase().includes(query))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Agregar canciones"
      size="md"
      preventClose={adding}
    >
      <div className="flex flex-col gap-4">
        <div className="relative">
          <Search
            size={15}
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
          />
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar canciones..."
            aria-label="Buscar canciones"
            className="pl-9"
          />
        </div>

        {error && (
          <p role="alert" className="text-xs text-error">
            {error}
          </p>
        )}

        <div className="max-h-72 space-y-1 overflow-y-auto pr-1">
          {loading ? (
            <p className="py-8 text-center text-xs text-muted">Cargando canciones...</p>
          ) : available.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted">
              {search ? 'No hay coincidencias.' : 'No hay canciones disponibles para agregar.'}
            </p>
          ) : (
            available.map((song) => {
              const checked = selectedIds.has(song.id)
              return (
                <button
                  key={song.id}
                  type="button"
                  onClick={() => toggle(song.id)}
                  aria-pressed={checked}
                  className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors ${
                    checked ? 'bg-primary-soft' : 'hover:bg-card-hover'
                  }`}
                >
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                      checked
                        ? 'border-primary bg-primary text-black'
                        : 'border-border-strong bg-transparent'
                    }`}
                  >
                    {checked && <Check size={12} strokeWidth={3} aria-hidden="true" />}
                  </span>
                  {song.thumbnail_url ? (
                    <img
                      src={song.thumbnail_url}
                      alt=""
                      className="h-8 w-8 shrink-0 rounded object-cover"
                    />
                  ) : (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-card-hover text-muted">
                      <Music2 size={14} aria-hidden="true" />
                    </div>
                  )}
                  <span className="truncate text-sm text-white">{song.title}</span>
                </button>
              )
            })
          )}
        </div>

        <Button
          variant="primary"
          loading={adding}
          disabled={selectedIds.size === 0 || adding}
          onClick={() => void handleConfirm()}
          className="w-full"
        >
          {adding
            ? 'Agregando...'
            : `Agregar ${selectedIds.size} canción${selectedIds.size !== 1 ? 'es' : ''}`}
        </Button>
      </div>
    </Modal>
  )
}
