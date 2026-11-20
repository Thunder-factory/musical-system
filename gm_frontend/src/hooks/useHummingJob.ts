import { useCallback, useEffect, useRef, useState } from 'react'

import { getHummingJob, isHummingJobActive } from '../api/modules/humming.api'
import type { HummingJob } from '../api/modules/humming.api'

/**
 * Sigue un tarareo mientras procesa él o alguna de sus mejoras con IA
 * (polling cada 2.5 s, 6 s ante errores de red).
 *
 * - `refresh` lo pide una vez, por ejemplo para renovar URLs firmadas.
 * - `resume` reanuda el polling, por ejemplo después de pedir una mejora.
 */
export function useHummingJob(jobId: string | null) {
  const [job, setJob] = useState<HummingJob | null>(null)
  const [loading, setLoading] = useState(false)
  const [pollTick, setPollTick] = useState(0)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastJobIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    // Solo se limpia el estado al cambiar de tarareo, no al reanudar el polling.
    if (lastJobIdRef.current !== jobId) {
      lastJobIdRef.current = jobId
      setJob(null)
      setLoading(Boolean(jobId))
    }
    if (!jobId) {
      return
    }

    let cancelled = false
    const poll = async () => {
      try {
        const data = await getHummingJob(jobId)
        if (cancelled) {
          return
        }
        setJob(data)
        setLoading(false)
        if (isHummingJobActive(data)) {
          timeoutRef.current = setTimeout(poll, 2500)
        }
      } catch {
        if (!cancelled) {
          timeoutRef.current = setTimeout(poll, 6000)
        }
      }
    }
    poll()

    return () => {
      cancelled = true
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [jobId, pollTick])

  const refresh = useCallback(async () => {
    if (!jobId) {
      return null
    }
    const data = await getHummingJob(jobId)
    setJob(data)
    return data
  }, [jobId])

  const resume = useCallback(() => setPollTick((tick) => tick + 1), [])

  return { job, loading, refresh, resume }
}
