import { useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'

import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import { toast } from '../../../store/toast.store'
import { getFaceSwapErrorMessage, getFaceSwapJob } from '../api/faceswap.api'
import type { FaceSwapJob, FaceSwapStatus } from '../types/faceswap.types'

const FINAL_STATES: FaceSwapStatus[] = ['completed', 'failed']
const POLL_MS = 4000
const RETRY_MS = 6000

export function useFaceSwapJob(jobId: string | null) {
  const [job, setJob] = useState<FaceSwapJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const upsertJob = useActiveJobsStore((s) => s.upsertJob)
  const removeJob = useActiveJobsStore((s) => s.removeJob)

  useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    setJob(null)
    setError(null)
    setLoadingStatus(Boolean(jobId))

    if (!jobId) {
      return
    }

    let cancelled = false
    let wasActive = false
    const storeKey = `faceswap:${jobId}`

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
        const data = await getFaceSwapJob(jobId)
        if (cancelled) {
          return
        }
        setJob(data)
        setError(data.error_message ?? null)
        setLoadingStatus(false)
        if (FINAL_STATES.includes(data.status)) {
          removeJob(storeKey)
          if (wasActive) {
            void refreshAuthBalance()
            if (data.status === 'completed') {
              toast.success('Video listo', 'Tu video de Cambiar caras ya está disponible.')
            }
          }
        } else {
          wasActive = true
          upsertJob({
            id: storeKey,
            kind: 'faceswap',
            label: data.template?.title || data.source_video_filename || 'Cambiar caras',
            route: '/faceswap',
            status: data.status,
            progressPct: Math.max(0, Math.min(100, Number(data.progress_pct) || 0)),
          })
          schedulePoll(POLL_MS)
        }
      } catch (err: unknown) {
        if (cancelled) {
          return
        }
        if (isAxiosError(err) && err.response?.status === 404) {
          removeJob(storeKey)
          setError(getFaceSwapErrorMessage(err))
          setLoadingStatus(false)
          return
        }
        schedulePoll(RETRY_MS)
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
  }, [jobId, removeJob, upsertJob])

  const progress = Math.max(0, Math.min(100, Number(job?.progress_pct) || 0))
  return { job, status: job?.status ?? null, progress, error, loadingStatus }
}
