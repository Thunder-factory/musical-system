import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getFaceSwapErrorMessage,
  getFaceSwapJobs,
  getFaceSwapTemplates,
} from '../api/faceswap.api'
import FaceSwapForm from '../components/faceswap-form'
import FaceSwapHistory from '../components/faceswap-history'
import FaceSwapOutputPanel from '../components/faceswap-output-panel'
import { useFaceSwapActions } from '../hooks/useFaceSwapActions'
import { useFaceSwapJob } from '../hooks/useFaceSwapJob'
import { FACESWAP_ACTIVE_STATUSES } from '../types/faceswap.types'

export default function FaceSwapPage() {
  const queryClient = useQueryClient()
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const skipRecoveryRef = useRef(false)
  const formRef = useRef<HTMLDivElement>(null)

  const templatesQuery = useQuery({
    queryKey: ['faceswap-templates'],
    queryFn: getFaceSwapTemplates,
    staleTime: 30 * 60 * 1000,
  })
  const jobsQuery = useQuery({ queryKey: ['faceswap-jobs'], queryFn: getFaceSwapJobs })
  const jobs = useMemo(() => jobsQuery.data ?? [], [jobsQuery.data])
  const templates = templatesQuery.data ?? []
  const { job, status, progress, error, loadingStatus } = useFaceSwapJob(activeJobId)

  function selectJob(id: string | null) {
    skipRecoveryRef.current = true
    setActiveJobId(id)
  }
  const actions = useFaceSwapActions({ activeJobId, selectJob })

  useEffect(() => {
    if (activeJobId || skipRecoveryRef.current) {
      return
    }
    const recover =
      jobs.find((j) => FACESWAP_ACTIVE_STATUSES.includes(j.status)) ??
      jobs.find((j) => j.status === 'completed')
    if (recover) {
      setActiveJobId(recover.id)
    }
  }, [activeJobId, jobs])

  useEffect(() => {
    if (status) {
      void queryClient.invalidateQueries({ queryKey: ['faceswap-jobs'] })
    }
  }, [queryClient, status, progress])

  const processing = Boolean(status && FACESWAP_ACTIVE_STATUSES.includes(status))
  const errorOf = (failed: boolean, err: unknown) => (failed ? getFaceSwapErrorMessage(err) : null)

  return (
    <div className="flex flex-col gap-5 px-4 pb-16 pt-4 sm:px-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Cambiar caras</h1>
        <p className="mt-1 text-sm text-muted">
          Pon tu cara en un video corto: sube una foto, elige el video y descárgalo listo.
        </p>
      </header>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div ref={formRef} className="min-w-0 scroll-mt-4">
          <FaceSwapForm
            templates={templates}
            templatesLoading={templatesQuery.isLoading}
            templatesError={errorOf(templatesQuery.isError, templatesQuery.error)}
            onRetryTemplates={() => void templatesQuery.refetch()}
            submitting={actions.submitting}
            processing={processing}
            apiNoCredits={actions.noCredits}
            error={actions.submitError}
            onSubmit={actions.submit}
          />
        </div>
        <FaceSwapOutputPanel
          jobId={activeJobId}
          title={job?.template?.title || job?.source_video_filename}
          status={status}
          progress={progress}
          error={error}
          loadingStatus={loadingStatus}
        />
      </div>

      <FaceSwapHistory
        jobs={jobs}
        templates={templates}
        isLoading={jobsQuery.isLoading}
        activeJobId={activeJobId}
        deletingId={actions.deletingId}
        error={actions.deleteError ?? errorOf(jobsQuery.isError, jobsQuery.error)}
        onSelect={selectJob}
        onDelete={actions.remove}
        onStart={() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
      />
    </div>
  )
}
