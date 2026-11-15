import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import AudioUploader from '../../components/stems/audio-uploader'
import StemProgress from '../../components/stems/stem-progress'
import StemResultCard from '../../components/stems/stem-result-card'
import { useStemJob } from '../../hooks/useStemJob'
import { getStemErrorMessage, getStemJobs, uploadAndSeparate } from '../../api/modules/stems.api'
import type { StemJob } from '../../api/modules/stems.api'

function JobHistoryRow({
  job,
  selected,
  onSelect,
}: {
  job: StemJob
  selected: boolean
  onSelect: () => void
}) {
  const statusColor: Record<string, string> = {
    queued: 'var(--text-subdued)',
    processing: 'var(--color-warning)',
    completed: 'var(--color-success)',
    failed: 'var(--color-error)',
  }
  const statusLabel: Record<string, string> = {
    queued: 'En cola',
    processing: 'Procesando',
    completed: 'Completado',
    failed: 'Error',
  }

  return (
    <button
      type="button"
      onClick={onSelect}
      className="bg-card-hover rounded-lg px-4 py-3 flex items-center justify-between gap-3 w-full text-left transition-colors"
      style={{
        border: `1px solid ${selected ? 'var(--color-primary)' : 'transparent'}`,
      }}
    >
      <div className="min-w-0">
        <p className="text-white text-sm font-medium truncate">{job.source_filename}</p>
        <p className="text-muted text-xs">{new Date(job.created_at).toLocaleString()}</p>
      </div>
      <span
        className="text-xs font-semibold px-2 py-1 rounded-full shrink-0"
        style={{
          background: 'var(--color-primary-soft)',
          color: statusColor[job.status] ?? 'var(--text-base)',
        }}
      >
        {statusLabel[job.status] ?? job.status}
        {['queued', 'processing'].includes(job.status) && ` · ${job.progress_pct}%`}
      </span>
    </button>
  )
}

export default function StemsPage() {
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploaderResetKey, setUploaderResetKey] = useState(0)
  const skipRecoveryRef = useRef(false)

  const { status, progress, stemFiles, error, loadingStatus } = useStemJob(activeJobId)

  const { data: history = [], refetch } = useQuery({
    queryKey: ['stem-jobs'],
    queryFn: getStemJobs,
  })

  const selectedJob = history.find((job) => job.id === activeJobId)

  useEffect(() => {
    if (!activeJobId && !skipRecoveryRef.current) {
      const jobToRecover =
        history.find((job) => ['queued', 'processing'].includes(job.status)) ??
        history.find((job) => job.status === 'completed')
      if (jobToRecover) {
        setActiveJobId(jobToRecover.id)
      }
    }
  }, [activeJobId, history])

  useEffect(() => {
    if (activeJobId && status) {
      refetch()
    }
  }, [activeJobId, refetch, status])

  useEffect(() => {
    if (status === 'completed') {
      setUploaderResetKey((key) => key + 1)
    }
  }, [status])

  async function handleSubmit(file: File) {
    if (uploading || loadingStatus || (status && !['completed', 'failed'].includes(status))) {
      return
    }

    setUploading(true)
    setUploadError(null)
    skipRecoveryRef.current = true
    setActiveJobId(null)
    try {
      const { job_id: jobId } = await uploadAndSeparate(file)
      setActiveJobId(jobId)
      skipRecoveryRef.current = false
      refetch()
    } catch (err: unknown) {
      setUploadError(getStemErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  const isProcessing = Boolean(
    loadingStatus || (status && !['completed', 'failed'].includes(status))
  )

  return (
    <div className="px-8 pt-7 pb-20 flex flex-col h-full">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-white text-[32px] font-bold tracking-tight">Separar pistas</h1>
          <p className="text-muted text-sm mt-1">Separa voz e instrumental en dos pistas.</p>
        </div>
      </div>

      <div className="flex flex-col gap-6" style={{ flex: 1 }}>
        <div className="w-full max-w-2xl mx-auto flex flex-col gap-4">
          <AudioUploader
            onSubmit={handleSubmit}
            resetKey={uploaderResetKey}
            onFileSelected={() => {
              skipRecoveryRef.current = true
              setActiveJobId(null)
              setUploadError(null)
            }}
            loading={uploading || isProcessing}
          />

          {uploadError && (
            <p className="text-sm px-1" style={{ color: 'var(--color-error)' }}>
              {uploadError}
            </p>
          )}

          {activeJobId && (
            <StemProgress
              status={status}
              progress={progress}
              error={error}
              loadingStatus={loadingStatus}
            />
          )}
        </div>

        <div
          className="grid gap-6 items-start min-h-0"
          style={{
            flex: 1,
            gridTemplateColumns: 'minmax(0, 0.9fr) minmax(0, 1.5fr)',
          }}
        >
          <div className="flex flex-col gap-3 min-w-0 min-h-0">
            <h2 className="text-white text-sm font-semibold">Historial de separaciones</h2>
            <div className="min-h-0 overflow-y-auto flex flex-col gap-3">
              {history.length === 0 ? (
                <p className="text-muted text-sm">Aún no tienes separaciones.</p>
              ) : (
                history.map((job) => (
                  <JobHistoryRow
                    key={job.id}
                    job={job}
                    selected={job.id === activeJobId}
                    onSelect={() => setActiveJobId(job.id)}
                  />
                ))
              )}
            </div>
          </div>

          <div className="min-w-0 flex flex-col gap-3">
            <h2 className="text-white text-sm font-semibold">Pistas generadas</h2>
            {status === 'completed' ? (
              <StemResultCard
                stemFiles={stemFiles}
                sourceFilename={selectedJob?.source_filename}
                createdAt={selectedJob?.created_at}
              />
            ) : (
              <div
                className="rounded-lg px-4 py-8 text-center"
                style={{
                  background: 'var(--bg-card-hover)',
                  border: '1px solid var(--bg-card-hover)',
                }}
              >
                <p className="text-muted text-sm">Selecciona una separación para ver sus pistas.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
