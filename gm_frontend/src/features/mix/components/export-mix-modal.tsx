import { useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'
import { CheckCircle2, Download, LoaderCircle } from 'lucide-react'

import { Button, Modal, Select } from '../../../components/ui'
import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import { toast } from '../../../store/toast.store'
import { startMixExport } from '../api/mix.api'
import { useMixExport } from '../hooks/useMixExport'

interface ExportMixModalProps {
  open: boolean
  mixId: string
  mixTitle: string
  exportState: {
    mutedClipIds: string[]
    soloClipIds: string[]
  }
  onClose: () => void
}

const FORMAT_OPTIONS = [
  { value: 'mp3', label: 'MP3' },
  { value: 'wav', label: 'WAV (sin compresión)' },
]

const QUALITY_OPTIONS = [
  { value: '128k', label: '128 kbps' },
  { value: '320k', label: '320 kbps (recomendado)' },
]

export default function ExportMixModal({
  open,
  mixId,
  mixTitle,
  exportState,
  onClose,
}: ExportMixModalProps) {
  const [format, setFormat] = useState<'mp3' | 'wav'>('mp3')
  const [quality, setQuality] = useState('320k')
  const [exportId, setExportId] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const { status, downloadUrl, error } = useMixExport(exportId)
  const { upsertJob, removeJob } = useActiveJobsStore()
  const syncedRef = useRef<string | null>(null)

  useEffect(() => {
    if (open) {
      setStartError(null)
      setExportId(null)
      syncedRef.current = null
    }
  }, [open])

  useEffect(() => {
    if (!exportId || syncedRef.current === `${exportId}:${status}`) {
      return
    }
    if (status === 'ready' || status === 'failed') {
      syncedRef.current = `${exportId}:${status}`
      removeJob(`mix-export:${exportId}`)
      void refreshAuthBalance()
      if (status === 'failed') {
        toast.error('No se pudo exportar el audio', error ?? undefined)
      } else {
        toast.success('Audio exportado correctamente')
      }
    }
  }, [exportId, status, error, removeJob])

  async function handleExport() {
    setStarting(true)
    setStartError(null)
    try {
      const res = await startMixExport(mixId, {
        format,
        quality,
        muted_clip_ids: exportState.mutedClipIds,
        solo_clip_ids: exportState.soloClipIds,
      })
      setExportId(res.export_id)
      upsertJob({
        id: `mix-export:${res.export_id}`,
        kind: 'mix',
        label: `Exportando ${mixTitle}`,
        route: `/mix/${mixId}`,
        status: 'processing',
      })
      void refreshAuthBalance()
    } catch (err) {
      const msg = isAxiosError<{ detail?: string }>(err)
        ? (err.response?.data?.detail ?? 'No se pudo iniciar la exportación.')
        : 'No se pudo iniciar la exportación. Inténtalo de nuevo.'
      setStartError(msg)
      toast.error('Error al exportar audio', msg)
    } finally {
      setStarting(false)
    }
  }

  const exporting = Boolean(starting || (exportId && status !== 'ready' && status !== 'failed'))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Exportar audio"
      size="sm"
      preventClose={exporting}
    >
      {!exportId ? (
        <div className="flex flex-col gap-4">
          <Select
            label="Formato"
            value={format}
            onChange={(v) => setFormat(v as 'mp3' | 'wav')}
            options={FORMAT_OPTIONS}
            disabled={starting}
          />

          {format === 'mp3' && (
            <Select
              label="Calidad"
              value={quality}
              onChange={setQuality}
              options={QUALITY_OPTIONS}
              disabled={starting}
            />
          )}

          {startError && (
            <p
              role="alert"
              className="rounded-lg border border-error-border bg-error-soft px-3 py-2 text-xs text-error"
            >
              {startError}
            </p>
          )}

          <Button
            variant="primary"
            costCredits={3}
            loading={starting}
            onClick={() => void handleExport()}
            className="mt-1 w-full"
          >
            {starting ? 'Iniciando...' : 'Exportar audio'}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 py-4 text-center">
          {status === 'ready' && downloadUrl ? (
            <>
              <CheckCircle2 size={38} className="text-success" aria-hidden="true" />
              <p className="text-base font-bold text-success">¡Audio listo para descargar!</p>
              <a
                href={downloadUrl}
                download
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-black transition-colors hover:bg-primary-hover"
              >
                <Download size={15} aria-hidden="true" />
                Descargar {format.toUpperCase()}
              </a>
            </>
          ) : status === 'failed' ? (
            <>
              <p className="text-sm text-error">
                Error al exportar: {error ?? 'Ocurrió un problema inesperado.'}
              </p>
              <Button variant="secondary" onClick={() => setExportId(null)}>
                Reintentar
              </Button>
            </>
          ) : (
            <>
              <LoaderCircle size={32} className="animate-spin text-primary" aria-hidden="true" />
              <p className="text-sm text-muted">Procesando tu mezcla de audio...</p>
            </>
          )}
        </div>
      )}
    </Modal>
  )
}
