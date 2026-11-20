import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { LoaderCircle } from 'lucide-react'

import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import { toast } from '../../../store/toast.store'
import {
  getHummingErrorMessage,
  getHummingJobs,
  isHummingJobActive,
  isNoCreditsError,
  uploadHumming,
} from '../api/humming.api'
import HummingHistory from '../components/humming-history'
import HummingRecorderCard from '../components/humming-recorder-card'
import HummingVersionsGrid from '../components/humming-versions-grid'
import { useHummingJob } from '../hooks/useHummingJob'

export default function HummingPage() {
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [noCredits, setNoCredits] = useState(false)
  const recoveredRef = useRef(false)
  const finishedJobRef = useRef<string | null>(null)

  const upsertJob = useActiveJobsStore((s) => s.upsertJob)
  const removeJob = useActiveJobsStore((s) => s.removeJob)

  const { job, loading, refresh, resume } = useHummingJob(activeJobId)
  const { data: history = [], refetch } = useQuery({
    queryKey: ['humming-jobs'],
    queryFn: getHummingJobs,
  })

  useEffect(() => {
    if (!recoveredRef.current && !activeJobId && history.length > 0) {
      recoveredRef.current = true
      setActiveJobId(history[0].id)
    }
  }, [activeJobId, history])

  useEffect(() => {
    if (job?.status) {
      void refetch()
    }
  }, [job?.status, refetch])

  useEffect(() => {
    if (!job) {
      return
    }
    if (isHummingJobActive(job)) {
      upsertJob({
        id: `humming:${job.id}`,
        kind: 'humming',
        label: job.title || 'Tarareo',
        route: '/humming',
        status: job.status === 'queued' ? 'queued' : 'processing',
        progressPct: job.progress,
      })
    } else {
      removeJob(`humming:${job.id}`)
      if (finishedJobRef.current !== job.id && job.status === 'completed') {
        finishedJobRef.current = job.id
        void refreshAuthBalance()
      }
    }
  }, [job, removeJob, upsertJob])

  const finishedEnhancements = job?.enhancements.filter(
    (item) => item.status === 'completed'
  ).length
  useEffect(() => {
    if (finishedEnhancements) {
      void refreshAuthBalance()
    }
  }, [finishedEnhancements])

  const busy = Boolean(job && ['queued', 'processing'].includes(job.status))

  async function handleSubmit(file: File, title: string): Promise<boolean> {
    setSubmitError(null)
    setNoCredits(false)
    try {
      const created = await uploadHumming(file, title)
      recoveredRef.current = true
      finishedJobRef.current = null
      setActiveJobId(created.id)
      upsertJob({
        id: `humming:${created.id}`,
        kind: 'humming',
        label: created.title || 'Tarareo',
        route: '/humming',
        status: 'queued',
      })
      void refetch()
      void refreshAuthBalance()
      toast.info('Tarareo enviado', 'Estamos detectando tu melodía.')
      return true
    } catch (error) {
      setNoCredits(isNoCreditsError(error))
      setSubmitError(
        isNoCreditsError(error)
          ? 'No tienes créditos suficientes.'
          : getHummingErrorMessage(error, 'No se pudo enviar el tarareo. Intenta de nuevo.')
      )
      return false
    }
  }

  return (
    <div className="flex flex-col gap-6 px-4 pb-20 pt-6 sm:px-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Tararear</h1>
        <p className="mt-1 text-sm text-muted">
          Tararea una melodía y conviértela en canciones instrumentales en distintos estilos.
        </p>
      </header>

      <div className="w-full max-w-2xl">
        <HummingRecorderCard
          busy={busy}
          onSubmit={handleSubmit}
          submitError={submitError}
          noCredits={noCredits}
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.6fr)]">
        <HummingHistory jobs={history} activeJobId={activeJobId} onSelect={setActiveJobId} />

        <section className="flex min-w-0 flex-col gap-3" aria-labelledby="humming-result-title">
          <h2 id="humming-result-title" className="text-sm font-semibold text-white">
            Tus canciones
          </h2>
          <div className="rounded-2xl border border-border bg-card p-5">
            {job ? (
              <HummingVersionsGrid
                job={job}
                refresh={refresh}
                onChosen={() => void refetch()}
                onEnhanceRequested={() => {
                  resume()
                  void refreshAuthBalance()
                }}
              />
            ) : loading ? (
              <p className="inline-flex items-center gap-2 text-sm text-muted">
                <LoaderCircle size={16} className="animate-spin" aria-hidden="true" /> Cargando…
              </p>
            ) : (
              <p className="text-sm text-muted">
                Graba tu primer tarareo para ver aquí las canciones.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
