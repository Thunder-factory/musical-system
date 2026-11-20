import { useEffect, useState, type FormEvent } from 'react'
import { Check, ListMusic, LoaderCircle, Plus } from 'lucide-react'

import { Button, EmptyState, FormField, Input, Modal } from '../../../components/ui'
import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'
import { toast } from '../../../store/toast.store'
import type { LibrarySong } from '../api/songs.api'

interface PlaylistSummary {
  id: string
  title: string
  song_count: number
}

interface AddToPlaylistModalProps {
  song: LibrarySong | null
  open: boolean
  onClose: () => void
}

export function AddToPlaylistModal({ song, open, onClose }: AddToPlaylistModalProps) {
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [addingId, setAddingId] = useState<string | null>(null)
  const [newTitle, setNewTitle] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (!open) {
      return
    }
    let cancelled = false
    setLoading(true)
    client
      .get<PlaylistSummary[]>(ENDPOINTS.playlists.list)
      .then(({ data }) => {
        if (!cancelled) {
          setPlaylists(data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          toast.error('No se pudieron cargar tus playlists')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [open])

  async function handleAdd(playlist: PlaylistSummary) {
    if (!song || addingId) {
      return
    }
    setAddingId(playlist.id)
    try {
      await client.post(ENDPOINTS.playlists.songs(playlist.id), { song_id: song.id })
      toast.success('Canción agregada', `Se añadió a "${playlist.title}".`)
      onClose()
    } catch {
      toast.error('No se pudo agregar', 'Intenta de nuevo en unos momentos.')
    } finally {
      setAddingId(null)
    }
  }

  async function handleCreateAndAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!song || !newTitle.trim() || creating) {
      return
    }
    setCreating(true)
    try {
      const { data: created } = await client.post<PlaylistSummary>(ENDPOINTS.playlists.list, {
        title: newTitle.trim(),
      })
      await client.post(ENDPOINTS.playlists.songs(created.id), { song_id: song.id })
      toast.success('Playlist creada', `Se añadió "${song.title}" a "${created.title}".`)
      setNewTitle('')
      onClose()
    } catch {
      toast.error('No se pudo crear la playlist')
    } finally {
      setCreating(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Agregar a playlist" size="sm">
      <div className="flex flex-col gap-5">
        {song && (
          <p className="text-xs text-muted">
            Canción seleccionada: <span className="font-semibold text-white">{song.title}</span>
          </p>
        )}

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted">
            <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
            Cargando playlists...
          </div>
        ) : playlists.length === 0 ? (
          <EmptyState
            icon={<ListMusic size={22} aria-hidden="true" />}
            title="Aún no tienes playlists"
            description="Crea una playlist abajo para guardar esta canción."
            className="py-6"
          />
        ) : (
          <ul className="flex max-h-56 flex-col gap-2 overflow-y-auto">
            {playlists.map((playlist) => {
              const busy = addingId === playlist.id
              return (
                <li key={playlist.id}>
                  <button
                    type="button"
                    disabled={Boolean(addingId)}
                    onClick={() => handleAdd(playlist)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-card-hover px-3.5 py-2.5 text-left transition-colors hover:border-primary disabled:opacity-50"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">{playlist.title}</p>
                      <p className="text-xs text-muted">
                        {playlist.song_count} {playlist.song_count === 1 ? 'canción' : 'canciones'}
                      </p>
                    </div>
                    {busy ? (
                      <LoaderCircle size={16} className="animate-spin text-primary" aria-hidden="true" />
                    ) : (
                      <Check size={16} className="shrink-0 text-muted" aria-hidden="true" />
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}

        <form onSubmit={handleCreateAndAdd} className="border-t border-border pt-4 flex flex-col gap-3">
          <FormField label="O crea una nueva playlist">
            <div className="flex gap-2">
              <Input
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Ej. Favoritas de noche"
                maxLength={120}
                disabled={creating}
              />
              <Button
                type="submit"
                variant="secondary"
                loading={creating}
                disabled={!newTitle.trim()}
                leftIcon={<Plus size={15} aria-hidden="true" />}
              >
                Crear
              </Button>
            </div>
          </FormField>
        </form>
      </div>
    </Modal>
  )
}

export default AddToPlaylistModal
