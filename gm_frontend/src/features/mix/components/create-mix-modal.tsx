import { useEffect, useState, type FormEvent } from 'react'

import { Button, FormField, Input, Modal } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { getSongDetail } from '../../songs/api/songs.api'
import { addClip, createMixProject, type MixProject } from '../api/mix.api'

interface CreateMixModalProps {
  open: boolean
  initialSongId?: string | null
  initialSongTitle?: string | null
  onClose: () => void
  onCreated: (project: MixProject) => void
}

export default function CreateMixModal({
  open,
  initialSongId,
  initialSongTitle,
  onClose,
  onCreated,
}: CreateMixModalProps) {
  const [title, setTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setTitle(initialSongTitle ? `Mix - ${initialSongTitle}` : '')
      setError(null)
    }
  }, [open, initialSongTitle])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = title.trim()
    if (!trimmed) {
      setError('Escribe un nombre para el proyecto.')
      return
    }
    setCreating(true)
    setError(null)
    try {
      const project = await createMixProject({ title: trimmed })
      if (initialSongId) {
        try {
          const detail = await getSongDetail(initialSongId)
          const endMs = Math.round((detail.audio_duration ?? 180) * 1000)
          await addClip(project.id, {
            song_id: detail.id,
            position: 0,
            start_time_ms: 0,
            end_time_ms: endMs > 0 ? endMs : 180_000,
          })
        } catch {
          toast.warning('Proyecto creado, pero no se pudo adjuntar la canción automáticamente.')
        }
      }
      toast.success('Proyecto creado', `"${project.title}" listo para editar.`)
      onCreated(project)
    } catch {
      setError('No se pudo crear el proyecto. Inténtalo de nuevo.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nuevo proyecto de mix"
      size="sm"
      preventClose={creating}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {initialSongTitle && (
          <p className="rounded-lg border border-primary-border bg-primary-soft px-3 py-2 text-xs text-primary">
            Se agregará <strong>{initialSongTitle}</strong> como primera pista del mix.
          </p>
        )}

        <FormField label="Nombre del proyecto" error={error ?? undefined} required>
          <Input
            value={title}
            onChange={(e) => {
              setTitle(e.target.value)
              setError(null)
            }}
            placeholder="Ej: Sesión de verano"
            autoFocus
            maxLength={120}
            disabled={creating}
          />
        </FormField>

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose} disabled={creating}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={creating} disabled={!title.trim()}>
            {creating ? 'Creando...' : 'Crear proyecto'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
