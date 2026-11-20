import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckCircle2, Download, LoaderCircle, RotateCw } from 'lucide-react'

import { Button } from '../../../components/ui'
import { getFaceSwapErrorMessage, getFaceSwapResultUrl } from '../api/faceswap.api'

interface Props {
  jobId: string
}

export default function FaceSwapResult({ jobId }: Props) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const retriedRef = useRef(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      setUrl(await getFaceSwapResultUrl(jobId))
    } catch (err: unknown) {
      setError(getFaceSwapErrorMessage(err))
    }
  }, [jobId])

  useEffect(() => {
    retriedRef.current = false
    setUrl(null)
    void load()
  }, [load])

  function onVideoError() {
    if (!retriedRef.current) {
      retriedRef.current = true
      void load()
    } else {
      setUrl(null)
      setError('No se pudo reproducir el video.')
    }
  }

  async function download() {
    setDownloading(true)
    try {
      const signed = await getFaceSwapResultUrl(jobId, true)
      const anchor = document.createElement('a')
      anchor.href = signed
      anchor.download = `faceswap-${jobId}.mp4`
      anchor.target = '_blank'
      anchor.rel = 'noopener noreferrer'
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
    } catch (err: unknown) {
      setError(getFaceSwapErrorMessage(err))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm font-semibold text-success">
          <CheckCircle2 size={16} aria-hidden="true" />
          Tu video está listo
        </p>
        <Button
          variant="secondary"
          size="sm"
          loading={downloading}
          onClick={() => void download()}
          leftIcon={<Download size={14} aria-hidden="true" />}
        >
          Descargar
        </Button>
      </div>
      {url ? (
        <video
          key={url}
          src={url}
          controls
          playsInline
          onError={onVideoError}
          className="max-h-[60vh] w-full rounded-lg bg-night object-contain"
        />
      ) : error ? (
        <div className="flex flex-col items-start gap-3 rounded-lg bg-card-hover px-4 py-4">
          <p className="text-sm text-error" role="alert">
            {error}
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void load()}
            leftIcon={<RotateCw size={14} aria-hidden="true" />}
          >
            Reintentar
          </Button>
        </div>
      ) : (
        <div className="flex h-48 items-center justify-center gap-2 rounded-lg bg-night text-sm text-muted">
          <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
          Cargando video…
        </div>
      )}
    </div>
  )
}
