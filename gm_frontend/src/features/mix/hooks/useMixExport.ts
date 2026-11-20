import { useEffect, useState } from 'react'

import { getMixExportStatus } from '../api/mix.api'

const FINAL_STATES = ['ready', 'failed']

export function useMixExport(exportId: string | null) {
  const [status, setStatus] = useState<string | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!exportId) {
      setStatus(null)
      setDownloadUrl(null)
      setError(null)
      return
    }
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const data = await getMixExportStatus(exportId)
        if (cancelled) {
          return
        }
        setStatus(data.status)
        if (data.download_url) {
          setDownloadUrl(data.download_url)
        }
        if (data.error_message) {
          setError(data.error_message)
        }
        if (!FINAL_STATES.includes(data.status)) {
          timer = window.setTimeout(poll, 4000)
        }
      } catch {
        if (!cancelled) {
          timer = window.setTimeout(poll, 8000)
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer !== undefined) {
        window.clearTimeout(timer)
      }
    }
  }, [exportId])

  return { status, downloadUrl, error }
}
