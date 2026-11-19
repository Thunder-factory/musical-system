import { useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'

import { authService } from '../api/auth-service'
import { getFaceSwapErrorMessage, getFaceSwapJob } from '../api/modules/faceswap.api'
import { useAuthStore } from '../store/auth.store'
import type { FaceSwapJob, FaceSwapStatus } from '../types/faceswap.types'

const FINAL_STATES: FaceSwapStatus[] = ['completed', 'failed']
const POLL_MS = 4000
const RETRY_MS = 6000

/**
 * Hook de polling del estado de un job de face swap (copia de useStemJob).
 * Consulta cada 4 s (6 s tras error de red) hasta que el job llega a un estado final.
 * Al completarse refresca el perfil para actualizar el saldo de créditos del sidebar.
 *
 * @param jobId - ID del FaceSwapJob a monitorear, o null si no hay job activo.
 */
export function useFaceSwapJob(jobId: string | null) {
  const [job, setJob] = useState<FaceSwapJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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

    const schedulePoll = (delay: number) => {
      if (!cancelled) {
        timeoutRef.current = setTimeout(poll, delay)
      }
    }

    const refreshBalance = async () => {
      try {
        useAuthStore.getState().setUser(await authService.getProfile())
      } catch {
        // El saldo se actualizará en la siguiente carga del perfil.
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
          if (wasActive && data.status === 'completed') {
            void refreshBalance()
          }
        } else {
          wasActive = true
          schedulePoll(POLL_MS)
        }
      } catch (err: unknown) {
        if (cancelled) {
          return
        }
        if (isAxiosError(err) && err.response?.status === 404) {
          // El job ya no existe (borrado o ajeno): se deja de sondear.
          setError(getFaceSwapErrorMessage(err))
          setLoadingStatus(false)
          return
        }
        // Reintenta con intervalo mayor ante errores de red.
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
  }, [jobId])

  const progress = Math.max(0, Math.min(100, Number(job?.progress_pct) || 0))
  return { job, status: job?.status ?? null, progress, error, loadingStatus }
}
