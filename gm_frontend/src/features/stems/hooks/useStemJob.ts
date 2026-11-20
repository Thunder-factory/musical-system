import { useEffect, useRef, useState } from 'react'

import { getStemJobStatus, type StemFile } from '../api/stems.api'

const FINAL_STATES = ['completed', 'failed']

export function useStemJob(jobId: string | null) {
  const [status, setStatus] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [stemFiles, setStemFiles] = useState<StemFile[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }

    setStatus(null)
    setProgress(0)
    setStemFiles([])
    setError(null)
    setLoadingStatus(Boolean(jobId))

    if (!jobId) {
      return
    }

    let cancelled = false

    const schedulePoll = (delay: number) => {
      if (!cancelled) {
        timeoutRef.current = setTimeout(poll, delay)
      }
    }

    const poll = async () => {
      if (cancelled) {
        return
      }
      try {
        const data = await getStemJobStatus(jobId)
        if (cancelled) {
          return
        }
        setStatus(data.status)
        setProgress(Math.max(0, Math.min(100, Number(data.progress_pct) || 0)))
        if (data.stem_files) {
          setStemFiles(data.stem_files)
        }
        setError(data.error_message ?? null)
        setLoadingStatus(false)
        if (!FINAL_STATES.includes(data.status)) {
          schedulePoll(3000)
        }
      } catch {
        if (!cancelled) {
          schedulePoll(6000)
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [jobId])

  return { status, progress, stemFiles, error, loadingStatus }
}
