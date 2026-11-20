import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AudioWaveform } from 'lucide-react'

import { EmptyState } from '../../../components/ui'
import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import { useAuthStore } from '../../../store/auth.store'
import { toast } from '../../../store/toast.store'
import {
  getStemErrorMessage,
  getStemJobs,
  isStemNoCreditsError,
  separateFromSong,
  STEM_CREDIT_COST,
  uploadAndSeparate,
  type StemJob,
} from '../api/stems.api'
import StemHistory from '../components/stem-history'
import StemResultCard from '../components/stem-result-card'
import StemSourcePanel, { type StemSourceTab } from '../components/stem-source-panel'
import { useStemJob } from '../hooks/useStemJob'

export default function StemsPage() {
  const [searchParams] = useSearchParams()
  const initialSongId = searchParams.get('songId')

  const [sourceTab, setSourceTab] = useState<StemSourceTab>('library')
  const [selectedSongId, setSelectedSongId] = useState<string | null>(initialSongId)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [noCreditsApi, setNoCreditsApi] = useState(false)
  const [uploaderResetKey, setUploaderResetKey] = useState(0)
  const skipRecoveryRef = useRef(false)
  const finishedRef = useRef<string | null>(null)

  const balance = useAuthStore((s) => s.user?.credit_balance ?? 0)
  const upsertJob = useActiveJobsStore((s) => s.upsertJob)
  const removeJob = useActiveJobsStore((s) => s.removeJob)

  const { status, progress, stemFiles, error, loadingStatus } = useStemJob(activeJobId)
  const { data: history = [], refetch } = useQuery({ queryKey: ['stem-jobs'], queryFn: getStemJobs })

  const selectedJob: StemJob | undefined = history.find((job) => job.id === activeJobId)
  const insufficientCredits = balance < STEM_CREDIT_COST

  useEffect(() => {
    if (initialSongId) {
      setSourceTab('library')
      setSelectedSongId(initialSongId)
    }
  }, [initialSongId])

  useEffect(() => {
    if (!activeJobId && !skipRecoveryRef.current && history.length > 0) {
      const recover =
        history.find((job) => ['queued', 'processing'].includes(job.status)) ??
        history.find((job) => job.status === 'completed')
      if (recover) {
        setActiveJobId(recover.id)
      }
    }
  }, [activeJobId, history])

  useEffect(() => {
    if (!activeJobId || !status) {
      return
    }
    void refetch()
    const key = `stems:${activeJobId}`
    if (status === 'queued' || status === 'processing') {
      upsertJob({
        id: key,
        kind: 'stems',
        label: selectedJob?.source_filename ?? 'Separar pistas',
        route: '/stems',
        status,
        progressPct: progress,
      })
      return
    }
    removeJob(key)
    if (finishedRef.current !== activeJobId) {
      finishedRef.current = activeJobId
      void refreshAuthBalance()
      if (status === 'completed') {
        setUploaderResetKey((k) => k + 1)
        toast.success('Pistas separadas', 'Ya puedes reproducir y descargar voz e instrumental.')
      }
    }
  }, [activeJobId, progress, refetch, removeJob, selectedJob?.source_filename, status, upsertJob])

  const isProcessing = Boolean(
    loadingStatus || (status && !['completed', 'failed'].includes(status))
  )

  async function runSeparation(label: string, action: () => Promise<{ job_id: string }>) {
    if (submitting || isProcessing) {
      return
    }
    setSubmitting(true)
    setSubmitError(null)
    setNoCreditsApi(false)
    skipRecoveryRef.current = true
    setActiveJobId(null)
    try {
      const { job_id: jobId } = await action()
      finishedRef.current = null
      setActiveJobId(jobId)
      skipRecoveryRef.current = false
      upsertJob({ id: `stems:${jobId}`, kind: 'stems', label, route: '/stems', status: 'queued' })
      void refreshAuthBalance()
      void refetch()
    } catch (err: unknown) {
      setNoCreditsApi(isStemNoCreditsError(err))
      setSubmitError(getStemErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-full flex-col gap-6 px-4 pb-20 pt-6 sm:px-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Separar pistas</h1>
        <p className="mt-1 text-sm text-muted">
          Extrae voz e instrumental de tus canciones o de un archivo propio.
        </p>
      </header>

      <StemSourcePanel
        sourceTab={sourceTab}
        selectedSongId={selectedSongId}
        balance={balance}
        insufficientCredits={insufficientCredits}
        noCreditsApi={noCreditsApi}
        submitting={submitting}
        isProcessing={isProcessing}
        uploaderResetKey={uploaderResetKey}
        submitError={submitError}
        activeJobId={activeJobId}
        status={status}
        progress={progress}
        error={error}
        loadingStatus={loadingStatus}
        onTabChange={setSourceTab}
        onSelectSong={(id) => {
          setSelectedSongId(id)
          setSubmitError(null)
        }}
        onFileSelected={() => {
          skipRecoveryRef.current = true
          setActiveJobId(null)
          setSubmitError(null)
        }}
        onSeparateSong={(songId, songTitle) =>
          void runSeparation(songTitle, () => separateFromSong(songId))
        }
        onSeparateFile={(file) => void runSeparation(file.name, () => uploadAndSeparate(file))}
      />

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.5fr)]">
        <StemHistory history={history} activeJobId={activeJobId} onSelect={setActiveJobId} />
        <section className="flex min-w-0 flex-col gap-3">
          <h2 className="text-sm font-semibold text-white">Pistas generadas</h2>
          {status === 'completed' ? (
            <StemResultCard
              stemFiles={stemFiles}
              sourceFilename={selectedJob?.source_filename}
              createdAt={selectedJob?.created_at}
            />
          ) : (
            <EmptyState
              icon={<AudioWaveform size={20} aria-hidden="true" />}
              title="Selecciona una separación"
              description="Elige una tarea del historial o inicia una nueva para reproducir sus pistas."
              className="py-8"
            />
          )}
        </section>
      </div>
    </div>
  )
}
