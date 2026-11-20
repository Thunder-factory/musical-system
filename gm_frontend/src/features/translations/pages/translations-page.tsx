import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileVideo, LoaderCircle } from 'lucide-react'

import { EmptyState } from '../../../components/ui'
import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import { useAuthStore } from '../../../store/auth.store'
import { toast } from '../../../store/toast.store'
import {
  createTranslation,
  getTranslationConfig,
  getTranslationErrorMessage,
  getTranslationJobs,
  isTranslationNoCreditsError,
} from '../api/translations.api'
import TranslationForm from '../components/translation-form'
import TranslationHistory from '../components/translation-history'
import TranslationProgress from '../components/translation-progress'
import TranslationResult from '../components/translation-result'
import { useTranslationJob } from '../hooks/useTranslationJob'
import { DEFAULT_TRANSLATION_CONFIG } from '../lib/translation-constants'

export default function TranslationsPage() {
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [language, setLanguage] = useState('es')
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [uploadPercent, setUploadPercent] = useState<number | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [noCreditsError, setNoCreditsError] = useState(false)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const autoSelectedRef = useRef(false)
  const finishedRef = useRef<string | null>(null)

  const balance = useAuthStore((s) => s.user?.credit_balance ?? 0)
  const upsertJob = useActiveJobsStore((s) => s.upsertJob)
  const removeJob = useActiveJobsStore((s) => s.removeJob)

  const { data: config = DEFAULT_TRANSLATION_CONFIG } = useQuery({
    queryKey: ['translation-config'],
    queryFn: getTranslationConfig,
    staleTime: 5 * 60 * 1000,
  })
  const { data: history = [], refetch } = useQuery({
    queryKey: ['translation-jobs'],
    queryFn: getTranslationJobs,
  })
  const { job, loading } = useTranslationJob(activeJobId)

  useEffect(() => {
    if (autoSelectedRef.current || activeJobId || history.length === 0) {
      return
    }
    autoSelectedRef.current = true
    const inProgress = history.find((item) => ['queued', 'processing'].includes(item.status))
    setActiveJobId((inProgress ?? history[0]).id)
  }, [activeJobId, history])

  useEffect(() => {
    if (!job) {
      return
    }
    void refetch()
    const key = `translation:${job.id}`
    if (job.status === 'queued' || job.status === 'processing') {
      upsertJob({
        id: key,
        kind: 'translation',
        label: job.song_title || job.source_filename,
        route: '/traducciones',
        status: job.status,
        progressPct: job.progress_pct,
      })
      return
    }
    removeJob(key)
    if (finishedRef.current !== job.id) {
      finishedRef.current = job.id
      void refreshAuthBalance()
      if (job.status === 'completed') {
        toast.success('Video traducido', 'Tu doblaje ya está listo para ver y descargar.')
      }
    }
  }, [job, refetch, removeJob, upsertJob])

  const busy =
    uploadPercent !== null || Boolean(job && ['queued', 'processing'].includes(job.status))
  const insufficientCredits = balance < config.credit_cost

  async function handleSubmit() {
    if (!file || busy) {
      return
    }
    setSubmitError(null)
    setNoCreditsError(false)
    setUploadPercent(0)
    autoSelectedRef.current = true
    setActiveJobId(null)
    try {
      const { job_id: newJobId } = await createTranslation({
        file,
        targetLanguage: language,
        title,
        artist,
        onUploadProgress: setUploadPercent,
      })
      finishedRef.current = null
      setActiveJobId(newJobId)
      upsertJob({
        id: `translation:${newJobId}`,
        kind: 'translation',
        label: title.trim() || file.name,
        route: '/traducciones',
        status: 'queued',
      })
      setFile(null)
      void refreshAuthBalance()
      void refetch()
    } catch (error) {
      setNoCreditsError(isTranslationNoCreditsError(error))
      setSubmitError(getTranslationErrorMessage(error))
    } finally {
      setUploadPercent(null)
    }
  }

  return (
    <div className="flex flex-col gap-6 px-4 pb-20 pt-6 sm:px-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Traducciones</h1>
        <p className="mt-1 text-sm text-muted">
          Dobla un video musical a otro idioma conservando la voz y el tono del cantante.
        </p>
      </header>

      <section className="mx-auto flex w-full max-w-2xl flex-col gap-4" aria-label="Nueva traducción">
        <TranslationForm
          config={config}
          file={file}
          fileError={fileError}
          language={language}
          title={title}
          artist={artist}
          busy={busy}
          uploading={uploadPercent !== null}
          insufficientCredits={insufficientCredits}
          noCreditsError={noCreditsError}
          balance={balance}
          submitError={submitError}
          onFileChange={(selected, err) => {
            setFile(selected)
            setFileError(err)
            setSubmitError(null)
            setNoCreditsError(false)
          }}
          onLanguageChange={setLanguage}
          onTitleChange={setTitle}
          onArtistChange={setArtist}
          onSubmit={() => void handleSubmit()}
        />

        <TranslationProgress job={job} uploadPercent={uploadPercent} />
      </section>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.5fr)]">
        <TranslationHistory history={history} activeJobId={activeJobId} onSelect={setActiveJobId} />

        <section className="flex min-w-0 flex-col gap-3" aria-label="Resultado">
          <h2 className="text-sm font-semibold text-white">Resultado</h2>
          {job?.status === 'completed' ? (
            <TranslationResult job={job} />
          ) : loading ? (
            <div className="flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 py-10 text-sm text-muted">
              <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
              Cargando…
            </div>
          ) : (
            <EmptyState
              icon={<FileVideo size={22} aria-hidden="true" />}
              title={
                job && ['queued', 'processing'].includes(job.status)
                  ? 'Traducción en curso'
                  : job?.status === 'failed'
                    ? 'Esta traducción no se completó'
                    : 'Aún no hay resultado seleccionado'
              }
              description={
                job && ['queued', 'processing'].includes(job.status)
                  ? 'El video doblado aparecerá aquí cuando termine el proceso.'
                  : 'Sube un video arriba o selecciona una traducción del historial.'
              }
            />
          )}
        </section>
      </div>
    </div>
  )
}
