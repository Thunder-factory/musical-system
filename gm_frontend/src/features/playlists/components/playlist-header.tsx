import { useState } from 'react'
import { ListMusic, LoaderCircle, Pause, Pencil, Play, Plus, Share2, Trash2 } from 'lucide-react'

import { Button, FormField, Input, Textarea } from '../../../components/ui'
import { getPlaylistCoverUrl, type Playlist } from '../api/playlists.api'

interface PlaylistHeaderProps {
  playlist: Playlist
  songCount: number
  isFirstPlaying: boolean
  loadingPlay: boolean
  sharing: boolean
  onPlayAll: () => void
  onOpenAdd: () => void
  onShare: () => void
  onDelete: () => void
  onSaveDetails: (title: string, description: string) => Promise<void>
}

export default function PlaylistHeader({
  playlist,
  songCount,
  isFirstPlaying,
  loadingPlay,
  sharing,
  onPlayAll,
  onOpenAdd,
  onShare,
  onDelete,
  onSaveDetails,
}: PlaylistHeaderProps) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(playlist.title)
  const [description, setDescription] = useState(playlist.description ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const coverUrl = getPlaylistCoverUrl(playlist)

  function startEdit() {
    setTitle(playlist.title)
    setDescription(playlist.description ?? '')
    setError(null)
    setEditing(true)
  }

  async function save() {
    if (!title.trim()) {
      setError('El nombre de la playlist no puede estar vacío.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSaveDetails(title.trim(), description.trim())
      setEditing(false)
    } catch {
      setError('No se pudo actualizar la playlist.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mb-6 flex flex-col gap-5 sm:flex-row sm:items-center">
      <div className="flex h-32 w-32 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-card-hover text-muted">
        {coverUrl ? (
          <img src={coverUrl} alt={playlist.title} className="h-full w-full object-cover" />
        ) : (
          <ListMusic size={42} aria-hidden="true" />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted">
          {playlist.type === 'manual' ? 'Playlist' : 'Playlist automática'}
        </p>

        {editing ? (
          <div className="max-w-lg space-y-2.5">
            <FormField label="Nombre" error={error ?? undefined} required>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} disabled={saving} />
            </FormField>
            <FormField label="Descripción">
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                disabled={saving}
              />
            </FormField>
            <div className="flex gap-2">
              <Button variant="primary" size="sm" loading={saving} onClick={() => void save()}>
                Guardar
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={saving}
                onClick={() => setEditing(false)}
              >
                Cancelar
              </Button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <h1 className="truncate text-3xl font-bold tracking-tight text-white">
                {playlist.title}
              </h1>
              <button
                type="button"
                onClick={startEdit}
                aria-label="Editar playlist"
                title="Editar playlist"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border text-muted transition-colors hover:border-border-strong hover:text-white"
              >
                <Pencil size={14} aria-hidden="true" />
              </button>
            </div>
            {playlist.description && (
              <p className="mt-1.5 text-sm text-muted">{playlist.description}</p>
            )}
          </>
        )}

        <p className="mt-2 text-xs text-muted">
          {songCount} canción{songCount !== 1 ? 'es' : ''}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2.5">
          <Button
            variant="primary"
            size="sm"
            disabled={songCount === 0 || loadingPlay}
            leftIcon={
              loadingPlay ? (
                <LoaderCircle size={14} className="animate-spin" />
              ) : isFirstPlaying ? (
                <Pause size={14} fill="currentColor" />
              ) : (
                <Play size={14} fill="currentColor" />
              )
            }
            onClick={onPlayAll}
          >
            Reproducir todo
          </Button>

          <Button
            variant="secondary"
            size="sm"
            leftIcon={<Plus size={14} />}
            onClick={onOpenAdd}
          >
            Agregar canciones
          </Button>

          <Button
            variant="secondary"
            size="sm"
            loading={sharing}
            leftIcon={<Share2 size={14} />}
            onClick={onShare}
            aria-label="Compartir playlist"
          >
            Compartir
          </Button>

          <Button
            variant="danger"
            size="sm"
            leftIcon={<Trash2 size={14} />}
            onClick={onDelete}
          >
            Eliminar
          </Button>
        </div>
      </div>
    </div>
  )
}
