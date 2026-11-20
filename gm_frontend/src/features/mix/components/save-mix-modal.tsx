import { useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'
import { CheckCircle2, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button, FormField, Input, Modal, Textarea } from '../../../components/ui'
import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import { toast } from '../../../store/toast.store'
import {
  startMixExport,
  updateMixProject,
  type MixProject,
} from '../api/mix.api'
import { useMixExport } from '../hooks/useMixExport'
import MixTagPicker from './mix-tag-picker'

interface SaveMixModalProps {
  open: boolean
  mix: MixProject
  exportState: {
    mutedClipIds: string[]
    soloClipIds: string[]
  }
  onClose: () => void
  onRenamed: (updated: MixProject) => void
}

export default function SaveMixModal({
  open,
  mix,
  exportState,
  onClose,
  onRenamed,
}: SaveMixModalProps) {
  const suggestedName = mix.title.replace(/^Mix\s*-\s*/i, '').trim()
  const [name, setName] = useState(suggestedName)
  const [description, setDescription] = useState(mix.description ?? '')
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([])
  const [starting, setStarting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [exportId, setExportId] = useState<string | null>(null)
  const { status, downloadUrl, error } = useMixExport(exportId)
  const { upsertJob, removeJob } = useActiveJobsStore()
  const syncedExportRef = useRef<string | null>(null)

  useEffect(() => {
    if (open) {
      setName(mix.title.replace(/^Mix\s*-\s*/i, '').trim())
      setDescription(mix.description ?? '')
      setFormError(null)
      setExportId(null)
      syncedExportRef.current = null
    }
  }, [open, mix.description, mix.title])

  useEffect(() => {
    if (!exportId || syncedExportRef.current === `${exportId}:${status}`) {
      return
    }
    if (status === 'ready' || status === 'failed') {
      syncedExportRef.current = `${exportId}:${status}`
      removeJob(`mix-publish:${exportId}`)
      void refreshAuthBalance()
      if (status === 'failed') {
        toast.error('Error al publicar el mix', error ?? undefined)
      } else {
        toast.success('Mix publicado en tu biblioteca')
      }
    }
  }, [exportId, status, error, removeJob])

  function toggleTag(id: number) {
    setSelectedTagIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  async function handleSave() {
    const trimmed = name.trim()
    if (!trimmed) {
      setFormError('Escribe un nombre para tu mix.')
      return
    }
    setFormError(null)
    setStarting(true)
    try {
      const updated = await updateMixProject(mix.id, {
        title: `Mix - ${trimmed}`,
        description: description.trim() || undefined,
        tag_ids: selectedTagIds.length > 0 ? selectedTagIds : undefined,
      })
      onRenamed(updated)

      const res = await startMixExport(mix.id, {
        format: 'mp3',
        quality: '320k',
        muted_clip_ids: exportState.mutedClipIds,
        solo_clip_ids: exportState.soloClipIds,
      })
      setExportId(res.export_id)
      upsertJob({
        id: `mix-publish:${res.export_id}`,
        kind: 'mix',
        label: `Publicando Mix - ${trimmed}`,
        route: `/mix/${mix.id}`,
        status: 'processing',
      })
      void refreshAuthBalance()
    } catch (err) {
      const msg = isAxiosError<{ detail?: string }>(err)
        ? (err.response?.data?.detail ?? 'No se pudo publicar el mix.')
        : 'No se pudo publicar el mix. Inténtalo de nuevo.'
      setFormError(msg)
      toast.error('No se pudo iniciar la publicación', msg)
    } finally {
      setStarting(false)
    }
  }

  const isProcessing = Boolean(exportId && status !== 'ready' && status !== 'failed')

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Publicar en Biblioteca"
      size="md"
      preventClose={starting || isProcessing}
    >
      {!exportId ? (
        <div className="flex flex-col gap-4">
          <FormField
            label="Nombre del mix"
            hint={`Se guardará en tu biblioteca como "Mix - ${name.trim() || '...'}"`}
            error={formError ?? undefined}
            required
          >
            <Input
              value={name}
              onChange={(e) => {
                setName(e.target.value)
                setFormError(null)
              }}
              placeholder="Ej: Noche de verano"
              autoFocus
              disabled={starting}
            />
          </FormField>

          <FormField label="Descripción (opcional)">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ej: Mezcla de ritmos suaves para el atardecer..."
              rows={2}
              disabled={starting}
            />
          </FormField>

          <MixTagPicker selectedIds={selectedTagIds} onToggle={toggleTag} />

          <Button
            variant="primary"
            costCredits={3}
            loading={starting}
            disabled={starting || !name.trim()}
            onClick={() => void handleSave()}
            className="mt-1 w-full"
          >
            {starting ? 'Iniciando...' : 'Publicar en Biblioteca'}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 py-4 text-center">
          {status === 'ready' && downloadUrl ? (
            <>
              <CheckCircle2 size={38} className="text-success" aria-hidden="true" />
              <p className="text-base font-bold text-success">¡Mix publicado en tu biblioteca!</p>
              <p className="text-sm text-muted">
                Disponible en{' '}
                <Link to="/library" className="font-semibold text-primary hover:underline">
                  Tu biblioteca
                </Link>{' '}
                como <strong className="text-white">Mix - {name.trim()}</strong>.
              </p>
              <audio key={downloadUrl} src={downloadUrl} controls autoPlay className="mt-2 w-full" />
            </>
          ) : status === 'failed' ? (
            <>
              <p className="text-sm text-error">
                Error al publicar{error ? `: ${error}` : '.'}
              </p>
              <Button variant="secondary" onClick={() => setExportId(null)}>
                Reintentar
              </Button>
            </>
          ) : (
            <>
              <LoaderCircle size={32} className="animate-spin text-primary" aria-hidden="true" />
              <p className="text-sm text-muted">
                Mezclando tu audio... Esto puede tardar alrededor de un minuto.
              </p>
            </>
          )}
        </div>
      )}
    </Modal>
  )
}
