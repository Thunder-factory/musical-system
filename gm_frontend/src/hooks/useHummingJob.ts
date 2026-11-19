import { useCallback, useEffect, useRef, useState } from 'react'

import { getHummingJob, HUMMING_FINAL_STATES } from '../api/modules/humming.api'
import type { HummingJob } from '../api/modules/humming.api'

/**
 * Sigue un tarareo hasta que termina (polling cada 2.5 s, 6 s ante errores de red).
 * `refresh` vuelve a pedirlo, por ejemplo para renovar URLs firmadas vencidas.
 */
export function useHummingJob(jobId: string | null) {
  const [job, setJob] = useState<HummingJob | null>(null)
  const [loading, setLoading] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    setJob(null)
    setLoading(Boolean(jobId))
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
        if (!HUMMING_FINAL_STATES.includes(data.status)) {
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
  }, [jobId])

  const refresh = useCallback(async () => {
    if (!jobId) {
      return null
    }
    const data = await getHummingJob(jobId)
    setJob(data)
    return data
  }, [jobId])

  return { job, loading, refresh }
}
