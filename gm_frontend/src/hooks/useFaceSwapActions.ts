import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import {
  createFaceSwapJob,
  deleteFaceSwapJob,
  getFaceSwapErrorMessage,
  isNoCreditsError,
} from '../api/modules/faceswap.api'
import type { CreateFaceSwapJobInput } from '../types/faceswap.types'

interface Options {
  activeJobId: string | null
  /** Selecciona el job activo (y desactiva la recuperación automática). */
  selectJob: (id: string | null) => void
}

/**
 * Acciones de la vista Cambiar caras: crear un job (subida) y borrar uno del historial.
 * Expone los estados de carga y error de cada acción.
 */
export function useFaceSwapActions({ activeJobId, selectJob }: Options) {
  const queryClient = useQueryClient()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [noCredits, setNoCredits] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const refreshJobs = () => queryClient.invalidateQueries({ queryKey: ['faceswap-jobs'] })

  async function submit(input: CreateFaceSwapJobInput) {
    setSubmitting(true)
    setSubmitError(null)
    setNoCredits(false)
    try {
      const { job_id: jobId } = await createFaceSwapJob(input)
      selectJob(jobId)
      void refreshJobs()
    } catch (err: unknown) {
      setNoCredits(isNoCreditsError(err))
      setSubmitError(getFaceSwapErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function remove(id: string) {
    setDeletingId(id)
    setDeleteError(null)
    try {
      await deleteFaceSwapJob(id)
      if (id === activeJobId) {
        selectJob(null)
      }
      await refreshJobs()
    } catch (err: unknown) {
      setDeleteError(getFaceSwapErrorMessage(err))
    } finally {
      setDeletingId(null)
    }
  }

  return { submit, remove, submitting, submitError, noCredits, deletingId, deleteError }
}
