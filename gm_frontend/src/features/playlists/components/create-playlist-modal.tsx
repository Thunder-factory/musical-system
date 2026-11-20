import { useEffect, useState } from 'react'

import { Button, FormField, Input, Modal, Textarea } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { getLibrary, type LibrarySong } from '../../songs/api/songs.api'
import { addSongToPlaylist, createPlaylist, type Playlist } from '../api/playlists.api'
import SongPickerList from './song-picker-list'

interface CreatePlaylistModalProps {
  open: boolean
  onClose: () => void
  onCreated: (playlist: Playlist) => void
}

export default function CreatePlaylistModal({
  open,
  onClose,
  onCreated,
}: CreatePlaylistModalProps) {
  const [step, setStep] = useState<'details' | 'songs'>('details')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [titleError, setTitleError] = useState<string | null>(null)
  const [library, setLibrary] = useState<LibrarySong[]>([])
  const [loadingLib, setLoadingLib] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (open) {
      setStep('details')
      setTitle('')
      setDescription('')
      setTitleError(null)
      setSelectedIds(new Set())
    }
  }, [open])

  async function handleNextStep() {
    if (!title.trim()) {
      setTitleError('Escribe un nombre para la playlist.')
      return
    }
    setTitleError(null)
    setStep('songs')
    setLoadingLib(true)
    try {
      setLibrary(await getLibrary())
    } catch {
      toast.error('No se pudo cargar tu biblioteca')
      setLibrary([])
    } finally {
      setLoadingLib(false)
    }
  }

  function toggleSong(id: string) {
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

  async function handleConfirmCreate(skipSongs = false) {
    const trimmed = title.trim()
    if (!trimmed || submitting) {
      return
    }
    setSubmitting(true)
    try {
      const created = await createPlaylist({
        title: trimmed,
        description: description.trim() || undefined,
      })
      const ids = skipSongs ? [] : Array.from(selectedIds)
      for (let i = 0; i < ids.length; i++) {
        await addSongToPlaylist(created.id, ids[i], i)
      }
      toast.success('Playlist creada', `"${created.title}" lista.`)
      onCreated({ ...created, song_count: ids.length })
    } catch {
      toast.error('No se pudo crear la playlist. Inténtalo de nuevo.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={step === 'details' ? 'Nueva playlist' : 'Agregar canciones'}
      size="md"
      preventClose={submitting}
    >
      {step === 'details' ? (
        <div className="flex flex-col gap-4">
          <FormField label="Nombre" error={titleError ?? undefined} required>
            <Input
              value={title}
              onChange={(e) => {
                setTitle(e.target.value)
                setTitleError(null)
              }}
              onKeyDown={(e) => e.key === 'Enter' && void handleNextStep()}
              placeholder="Ej: Favoritas para entrenar"
              autoFocus
            />
          </FormField>

          <FormField label="Descripción (opcional)">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Una breve descripción de tu playlist..."
              rows={2}
            />
          </FormField>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={onClose}>
              Cancelar
            </Button>
            <Button variant="primary" disabled={!title.trim()} onClick={() => void handleNextStep()}>
              Siguiente →
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>Selecciona las canciones para “{title.trim()}”.</span>
            <span className="font-semibold text-primary">
              {selectedIds.size} seleccionada{selectedIds.size !== 1 ? 's' : ''}
            </span>
          </div>

          <SongPickerList
            songs={library}
            loading={loadingLib}
            selectedIds={selectedIds}
            onToggle={toggleSong}
          />

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setStep('details')} disabled={submitting}>
              ← Atrás
            </Button>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                disabled={submitting}
                onClick={() => void handleConfirmCreate(true)}
              >
                Crear vacía
              </Button>
              <Button
                variant="primary"
                loading={submitting}
                onClick={() => void handleConfirmCreate(false)}
              >
                {submitting
                  ? 'Creando...'
                  : selectedIds.size > 0
                    ? `Crear con ${selectedIds.size}`
                    : 'Crear playlist'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  )
}
