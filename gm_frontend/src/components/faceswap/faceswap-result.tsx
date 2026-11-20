import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckCircle2, Download, LoaderCircle, RotateCw } from 'lucide-react'

import { getFaceSwapErrorMessage, getFaceSwapResultUrl } from '../../api/modules/faceswap.api'
import { BTN_OUTLINE } from './faceswap-ui'

interface Props {
  jobId: string
}

/** Reproduce el MP4 resultante (URL firmada) y permite descargarlo. */
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
    // La URL firmada dura 1 h: se vuelve a pedir una sola vez.
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
      window.open(await getFaceSwapResultUrl(jobId, true), '_blank', 'noopener')
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
        <button type="button" className={BTN_OUTLINE} onClick={download} disabled={downloading}>
          {downloading ? (
            <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <Download size={14} aria-hidden="true" />
          )}
          Descargar
        </button>
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
          <p className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
            {error}
          </p>
          <button type="button" className={BTN_OUTLINE} onClick={() => void load()}>
            <RotateCw size={14} aria-hidden="true" />
            Reintentar
          </button>
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
