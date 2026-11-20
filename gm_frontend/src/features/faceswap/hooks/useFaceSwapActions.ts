import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import { toast } from '../../../store/toast.store'
import {
  createFaceSwapJob,
  deleteFaceSwapJob,
  getFaceSwapErrorMessage,
  isNoCreditsError,
} from '../api/faceswap.api'
import type { CreateFaceSwapJobInput } from '../types/faceswap.types'

interface Options {
  activeJobId: string | null
  selectJob: (id: string | null) => void
}

export function useFaceSwapActions({ activeJobId, selectJob }: Options) {
  const queryClient = useQueryClient()
  const upsertJob = useActiveJobsStore((s) => s.upsertJob)
  const removeJob = useActiveJobsStore((s) => s.removeJob)

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
      upsertJob({
        id: `faceswap:${jobId}`,
        kind: 'faceswap',
        label: 'Cambiar caras',
        route: '/faceswap',
        status: 'queued',
      })
      void refreshAuthBalance()
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
      removeJob(`faceswap:${id}`)
      if (id === activeJobId) {
        selectJob(null)
      }
      await refreshJobs()
      toast.success('Video eliminado')
    } catch (err: unknown) {
      setDeleteError(getFaceSwapErrorMessage(err))
    } finally {
      setDeletingId(null)
    }
  }

  return { submit, remove, submitting, submitError, noCredits, deletingId, deleteError }
}
