import { useCallback, useEffect, useRef, useState } from 'react'

import { getHummingJob, isHummingJobActive } from '../api/humming.api'
import type { HummingJob } from '../api/humming.api'

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
    void poll()

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
