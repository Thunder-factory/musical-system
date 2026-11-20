import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, FileVideo, Languages, LoaderCircle, Mic2 } from 'lucide-react'

import {
  createTranslation,
  getTranslationConfig,
  getTranslationErrorMessage,
  getTranslationFileUrl,
  getTranslationJobs,
} from '../../api/modules/translations.api'
import type {
  TranslationConfig,
  TranslationFileKind,
  TranslationJob,
} from '../../api/modules/translations.api'
import { useTranslationJob } from '../../hooks/useTranslationJob'

// ─── Textos ──────────────────────────────────────────────────────────────────

const LANGUAGE_NAMES: Record<string, string> = {
  en: 'Inglés',
  es: 'Español',
  fr: 'Francés',
  zh: 'Chino',
}

/** Etapas del pipeline en el orden en que ocurren. */
const STAGES: { key: string; label: string }[] = [
  { key: 'descargando', label: 'Descargando video' },
  { key: 'extrayendo', label: 'Extrayendo audio' },
  { key: 'separando', label: 'Separando la voz' },
  { key: 'transcribiendo', label: 'Transcribiendo la letra' },
  { key: 'traduciendo', label: 'Traduciendo y adaptando' },
  { key: 'sintetizando', label: 'Generando la nueva voz' },
  { key: 'mezclando', label: 'Mezclando con el video' },
  { key: 'subiendo', label: 'Guardando el resultado' },
]

const EXTRA_STAGE_LABELS: Record<string, string> = {
  subiendo_video: 'Subiendo tu video…',
  en_cola: 'En cola…',
  completado: 'Completado',
}

const STATUS_LABELS: Record<string, string> = {
  queued: 'En cola',
  processing: 'Procesando',
  completed: 'Completado',
  failed: 'Error',
}

const STATUS_COLORS: Record<string, string> = {
  queued: 'var(--text-subdued)',
  processing: 'var(--color-warning)',
  completed: 'var(--color-success)',
  failed: 'var(--color-error)',
}

const LYRICS_SOURCE: Record<string, string> = {
  usuario: 'Letra enviada por el usuario',
  lrclib: 'Letra encontrada en LRCLIB',
  whisper: 'Letra transcrita con Whisper',
}

const DEFAULT_CONFIG: TranslationConfig = {
  languages: Object.entries(LANGUAGE_NAMES).map(([code, label]) => ({ code, label })),
  allowed_extensions: ['.mp4', '.mov', '.webm'],
  max_duration_seconds: 300,
  max_file_size_mb: 300,
  credit_cost: 3,
}

// ─── Utilidades ──────────────────────────────────────────────────────────────

function stageLabel(stage: string): string {
  return STAGES.find((s) => s.key === stage)?.label ?? EXTRA_STAGE_LABELS[stage] ?? stage
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatSeconds(total: number | null | undefined): string {
  if (total == null || Number.isNaN(total)) {return '—'}
  const minutes = Math.floor(total / 60)
  const seconds = Math.floor(total % 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

/** Lee la duración del video en el navegador antes de subirlo. */
function readVideoDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const video = document.createElement('video')
    video.preload = 'metadata'
    const done = (value: number | null) => {
      URL.revokeObjectURL(url)
      resolve(value)
    }
    video.onloadedmetadata = () => done(Number.isFinite(video.duration) ? video.duration : null)
    video.onerror = () => done(null)
    video.src = url
  })
}

// ─── Selector de video ───────────────────────────────────────────────────────

function VideoPicker({
  config,
  file,
  disabled,
  onChange,
}: {
  config: TranslationConfig
  file: File | null
  disabled: boolean
  onChange: (file: File | null, error: string | null) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    if (!file && inputRef.current) {inputRef.current.value = ''}
  }, [file])

  async function handleFile(candidate: File) {
    const extension = '.' + (candidate.name.split('.').pop() ?? '').toLowerCase()
    if (!config.allowed_extensions.includes(extension)) {
      onChange(null, 'Solo se aceptan videos MP4, MOV o WebM.')
      return
    }
    if (candidate.size > config.max_file_size_mb * 1024 * 1024) {
      onChange(null, `El video supera el límite de ${config.max_file_size_mb} MB (${formatSize(candidate.size)}).`)
      return
    }
    const duration = await readVideoDuration(candidate)
    if (duration != null && duration > config.max_duration_seconds) {
      onChange(
        null,
        `El video dura ${formatSeconds(duration)}; el máximo es ${formatSeconds(config.max_duration_seconds)}.`,
      )
      return
    }
    onChange(candidate, null)
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    if (disabled) {return}
    const dropped = event.dataTransfer.files[0]
    if (dropped) {void handleFile(dropped)}
  }

  function onInput(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0]
    if (selected) {void handleFile(selected)}
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      onKeyDown={(event) => {
        if (!disabled && (event.key === 'Enter' || event.key === ' ')) {inputRef.current?.click()}
      }}
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) {setDragging(true)}
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className="border-2 border-dashed rounded-xl p-6 flex flex-col items-center gap-2 text-center transition-colors"
      style={{
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
        borderColor: dragging ? 'var(--color-primary)' : 'var(--bg-card-hover)',
        background: dragging ? 'var(--color-primary-soft)' : 'transparent',
      }}
    >
      <FileVideo size={36} strokeWidth={1.6} style={{ color: 'var(--color-primary)' }} aria-hidden="true" />
      {file ? (
        <>
          <p className="text-white text-sm font-medium break-all">{file.name}</p>
          <p className="text-muted text-xs">
            {`${file.name.split('.').pop()?.toUpperCase()} · ${formatSize(file.size)} · toca para cambiarlo`}
          </p>
        </>
      ) : (
        <>
          <p className="text-white text-sm font-medium">
            Arrastra un video musical aquí o <span style={{ color: 'var(--color-primary)' }}>selecciona</span>
          </p>
          <p className="text-muted text-xs">
            MP4, MOV o WebM — hasta {config.max_file_size_mb} MB y {config.max_duration_seconds / 60} minutos
          </p>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
        className="hidden"
        onChange={onInput}
        disabled={disabled}
      />
    </div>
  )
}

// ─── Progreso por etapas ─────────────────────────────────────────────────────

function StageProgress({ job, uploadPercent }: { job: TranslationJob | null; uploadPercent: number | null }) {
  if (uploadPercent !== null) {
    return (
      <ProgressBar label={`Subiendo tu video… ${uploadPercent}%`} percent={uploadPercent} tone="primary" />
    )
  }
  if (!job || job.status === 'completed') {return null}

  const failed = job.status === 'failed'
  const currentIndex = STAGES.findIndex((stage) => stage.key === job.stage)

  return (
    <div className="flex flex-col gap-4 rounded-xl p-4" style={{ background: 'var(--bg-card)' }}>
      <ProgressBar
        label={failed ? 'La traducción falló' : stageLabel(job.stage)}
        percent={job.progress_pct}
        tone={failed ? 'error' : 'primary'}
      />
      {failed ? (
        job.error_message && (
          <p className="text-xs" style={{ color: 'var(--color-error)' }}>
            {job.error_message} Tus créditos no fueron cobrados.
          </p>
        )
      ) : (
        <ol className="grid grid-cols-2 sm:grid-cols-4 gap-2" aria-label="Etapas del doblaje">
          {STAGES.map((stage, index) => {
            const done = currentIndex > index
            const active = currentIndex === index
            return (
              <li
                key={stage.key}
                className="flex items-center gap-2 text-xs rounded-lg px-2 py-1.5"
                style={{
                  background: active ? 'var(--color-primary-soft)' : 'transparent',
                  color: done ? 'var(--color-success)' : active ? 'var(--text-base)' : 'var(--text-subdued)',
                }}
              >
                {active ? (
                  <LoaderCircle size={12} className="animate-spin shrink-0" aria-hidden="true" />
                ) : (
                  <span aria-hidden="true" className="shrink-0">{done ? '✓' : '•'}</span>
                )}
                <span className="truncate">{stage.label}</span>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

function ProgressBar({ label, percent, tone }: { label: string; percent: number; tone: 'primary' | 'error' }) {
  const safe = Math.max(0, Math.min(100, Number(percent) || 0))
  const color = tone === 'error' ? 'var(--color-error)' : 'var(--color-primary)'
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium" style={{ color: tone === 'error' ? color : 'var(--text-base)' }}>
          {label}
        </span>
        <span className="text-xs text-muted">{safe}%</span>
      </div>
      <div
        className="h-2 rounded-full overflow-hidden"
        style={{ background: 'var(--bg-card-hover)' }}
        role="progressbar"
        aria-valuenow={safe}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${safe}%`, background: color }} />
      </div>
    </div>
  )
}

// ─── Historial ───────────────────────────────────────────────────────────────

function HistoryRow({ job, selected, onSelect }: { job: TranslationJob; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="bg-card-hover rounded-lg px-4 py-3 flex items-center justify-between gap-3 w-full text-left transition-colors"
      style={{ border: `1px solid ${selected ? 'var(--color-primary)' : 'transparent'}` }}
    >
      <div className="min-w-0">
        <p className="text-white text-sm font-medium truncate">{job.song_title || job.source_filename}</p>
        <p className="text-muted text-xs">
          → {LANGUAGE_NAMES[job.target_language] ?? job.target_language} ·{' '}
          {new Date(job.created_at).toLocaleString()}
        </p>
      </div>
      <span
        className="text-xs font-semibold px-2 py-1 rounded-full shrink-0"
        style={{ background: 'var(--color-primary-soft)', color: STATUS_COLORS[job.status] }}
      >
        {STATUS_LABELS[job.status] ?? job.status}
        <span>
          {['queued', 'processing'].includes(job.status) ? ` · ${job.progress_pct}%` : ''}
        </span>
      </span>
    </button>
  )
}

// ─── Resultado ───────────────────────────────────────────────────────────────

function ResultPanel({ job }: { job: TranslationJob }) {
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [videoError, setVideoError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<TranslationFileKind | null>(null)

  useEffect(() => {
    let cancelled = false
    setVideoUrl(null)
    setVideoError(null)
    getTranslationFileUrl(job.id, 'video')
      .then((url) => !cancelled && setVideoUrl(url))
      .catch(() => !cancelled && setVideoError('No se pudo cargar el video.'))
    return () => {
      cancelled = true
    }
  }, [job.id])

  async function download(kind: TranslationFileKind) {
    setDownloading(kind)
    try {
      window.location.href = await getTranslationFileUrl(job.id, kind, true)
    } finally {
      setDownloading(null)
    }
  }

  const lyrics = job.lyrics
  const source = lyrics?.fuente_letra ? LYRICS_SOURCE[lyrics.fuente_letra] : null
  const showOriginal = Boolean(lyrics?.frases.some((phrase) => phrase.original))

  return (
    <div className="flex flex-col gap-4 rounded-xl p-4" style={{ background: 'var(--bg-card)' }}>
      {job.mode === 'simulated' && (
        <p
          className="text-xs rounded-lg px-3 py-2"
          style={{ background: 'var(--color-primary-soft)', color: 'var(--color-primary-hover)' }}
        >
          <strong>Modo simulado:</strong> el video conserva su audio original, la voz es un tono de prueba y la letra
          es de demostración. Sirve para probar el flujo completo sin gastar GPU.
        </p>
      )}

      <div className="rounded-lg overflow-hidden aspect-video flex items-center justify-center" style={{ background: '#000' }}>
        {videoUrl ? (
          <video src={videoUrl} controls playsInline className="w-full h-full" />
        ) : videoError ? (
          <p className="text-sm" style={{ color: 'var(--color-error)' }}>{videoError}</p>
        ) : (
          <LoaderCircle className="animate-spin" style={{ color: 'var(--text-subdued)' }} aria-label="Cargando video" />
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <DownloadButton label="Descargar video" busy={downloading === 'video'} onClick={() => download('video')} icon={<Download size={16} aria-hidden="true" />} />
        <DownloadButton label="Solo la voz (MP3)" busy={downloading === 'audio'} onClick={() => download('audio')} icon={<Mic2 size={16} aria-hidden="true" />} secondary />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <dt className="text-muted">Idiomas</dt>
        <dd className="text-white">
          {LANGUAGE_NAMES[lyrics?.idioma_origen ?? ''] ?? lyrics?.idioma_origen ?? '—'} →{' '}
          {LANGUAGE_NAMES[job.target_language] ?? job.target_language}
        </dd>
        <dt className="text-muted">Duración</dt>
        <dd className="text-white">{formatSeconds(job.source_duration_seconds)}</dd>
        {source && (
          <>
            <dt className="text-muted">Origen de la letra</dt>
            <dd className="text-white">{source}</dd>
          </>
        )}
        {typeof job.details.modelo_llm === 'string' && job.details.modelo_llm !== 'simulado' && (
          <>
            <dt className="text-muted">Modelo de traducción</dt>
            <dd className="text-white">{job.details.modelo_llm}</dd>
          </>
        )}
        {typeof job.details.segundos_proceso === 'number' && (
          <>
            <dt className="text-muted">Tiempo de proceso</dt>
            <dd className="text-white">{formatSeconds(job.details.segundos_proceso)}</dd>
          </>
        )}
        <dt className="text-muted">Créditos</dt>
        <dd className="text-white">{job.credits_used}</dd>
      </dl>
      {typeof job.details.motivo_nivel_llm === 'string' && job.details.motivo_nivel_llm && (
        <p className="text-muted text-xs">{`Nota: ${job.details.motivo_nivel_llm}`}</p>
      )}

      {lyrics && lyrics.frases.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-white text-sm font-semibold">Letra traducida</h3>
          {lyrics.resumen && <p className="text-muted text-xs italic">{lyrics.resumen}</p>}
          <div className="max-h-72 overflow-y-auto rounded-lg" style={{ border: '1px solid var(--border)' }}>
            <table className="w-full text-xs">
              <thead className="sticky top-0" style={{ background: 'var(--bg-card-hover)' }}>
                <tr className="text-left text-muted">
                  <th className="px-3 py-2 font-medium w-16">Tiempo</th>
                  {showOriginal && <th className="px-3 py-2 font-medium">Original</th>}
                  <th className="px-3 py-2 font-medium">Traducción</th>
                </tr>
              </thead>
              <tbody>
                {lyrics.frases.map((phrase, index) => (
                  <tr key={index} style={{ borderTop: '1px solid var(--border)' }}>
                    <td className="px-3 py-2 text-muted tabular-nums">{formatSeconds(phrase.inicio)}</td>
                    {showOriginal && <td className="px-3 py-2 text-muted">{phrase.original ?? ''}</td>}
                    <td className="px-3 py-2 text-white">{phrase.texto}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function DownloadButton({
  label,
  icon,
  busy,
  secondary = false,
  onClick,
}: {
  label: string
  icon: React.ReactNode
  busy: boolean
  secondary?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-opacity"
      style={{
        background: secondary ? 'var(--bg-card-hover)' : 'var(--color-primary)',
        color: secondary ? 'var(--text-base)' : 'var(--bg-base)',
        opacity: busy ? 0.6 : 1,
      }}
    >
      <span className="flex items-center" aria-hidden="true">
        {busy ? <LoaderCircle size={16} className="animate-spin" /> : icon}
      </span>
      <span>{label}</span>
    </button>
  )
}

// ─── Página ──────────────────────────────────────────────────────────────────

export default function TranslationsPage() {
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [language, setLanguage] = useState('es')
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [uploadPercent, setUploadPercent] = useState<number | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const autoSelectedRef = useRef(false)

  const { data: config = DEFAULT_CONFIG } = useQuery({
    queryKey: ['translation-config'],
    queryFn: getTranslationConfig,
    staleTime: 5 * 60 * 1000,
  })
  const { data: history = [], refetch } = useQuery({
    queryKey: ['translation-jobs'],
    queryFn: getTranslationJobs,
  })
  const { job, loading } = useTranslationJob(activeJobId)

  // Al entrar, retoma el trabajo en curso o muestra el último completado.
  useEffect(() => {
    if (autoSelectedRef.current || activeJobId || history.length === 0) {return}
    autoSelectedRef.current = true
    const inProgress = history.find((item) => ['queued', 'processing'].includes(item.status))
    setActiveJobId((inProgress ?? history[0]).id)
  }, [activeJobId, history])

  // Refresca el historial cuando cambia el estado del trabajo seleccionado.
  useEffect(() => {
    if (job) {void refetch()}
  }, [job?.status, job?.stage, refetch]) // eslint-disable-line react-hooks/exhaustive-deps

  const busy = uploadPercent !== null || Boolean(job && ['queued', 'processing'].includes(job.status))
  const canSubmit = Boolean(file) && !busy

  const languageOptions = useMemo(
    () => config.languages.map((item) => ({ ...item, label: LANGUAGE_NAMES[item.code] ?? item.label })),
    [config.languages],
  )

  async function handleSubmit() {
    if (!file || busy) {return}
    setSubmitError(null)
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
      setActiveJobId(newJobId)
      setFile(null)
      void refetch()
    } catch (error) {
      setSubmitError(getTranslationErrorMessage(error))
    } finally {
      setUploadPercent(null)
    }
  }

  return (
    <div className="px-4 sm:px-8 pt-7 pb-20 flex flex-col gap-6">
      <header>
        <h1 className="text-white text-[32px] font-bold tracking-tight flex items-center gap-3">
          <Languages size={28} style={{ color: 'var(--color-primary)' }} aria-hidden="true" />
          Traducciones
        </h1>
        <p className="text-muted text-sm mt-1">
          Dobla un video musical a otro idioma conservando la voz y el tono del cantante.
        </p>
      </header>

      <section className="w-full max-w-2xl mx-auto flex flex-col gap-4" aria-label="Nueva traducción">
        <VideoPicker
          config={config}
          file={file}
          disabled={busy}
          onChange={(selected, error) => {
            setFile(selected)
            setFileError(error)
            setSubmitError(null)
          }}
        />
        {fileError && <p className="text-sm px-1" style={{ color: 'var(--color-error)' }}>{fileError}</p>}

        <fieldset className="flex flex-col gap-2" disabled={busy}>
          <legend className="text-white text-sm font-semibold mb-2">Idioma de destino</legend>
          <div className="flex flex-wrap gap-2">
            {languageOptions.map((option) => {
              const selected = option.code === language
              return (
                <button
                  key={option.code}
                  type="button"
                  onClick={() => setLanguage(option.code)}
                  aria-pressed={selected}
                  className="px-4 py-2 rounded-full text-sm font-medium transition-colors"
                  style={{
                    background: selected ? 'var(--color-primary)' : 'var(--bg-card-hover)',
                    color: selected ? 'var(--bg-base)' : 'var(--text-base)',
                  }}
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        </fieldset>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted">
            Título de la canción (opcional)
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={200}
              disabled={busy}
              placeholder="Ej.: Bohemian Rhapsody"
              className="rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: 'var(--bg-card-hover)', border: '1px solid var(--border-strong)' }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            Artista (opcional)
            <input
              value={artist}
              onChange={(event) => setArtist(event.target.value)}
              maxLength={200}
              disabled={busy}
              placeholder="Ej.: Queen"
              className="rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: 'var(--bg-card-hover)', border: '1px solid var(--border-strong)' }}
            />
          </label>
        </div>
        <p className="text-muted text-xs -mt-2">
          Con el título y el artista se busca la letra oficial para que la traducción sea más precisa.
        </p>

        <div className="flex items-center justify-end gap-3">
          <span className="text-muted text-xs">{config.credit_cost} créditos</span>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold transition-opacity"
            style={{
              background: 'var(--color-primary)',
              color: 'var(--bg-base)',
              opacity: canSubmit ? 1 : 0.5,
              cursor: canSubmit ? 'pointer' : 'not-allowed',
            }}
          >
            <span className="flex items-center" aria-hidden="true">
              {busy ? <LoaderCircle size={16} className="animate-spin" /> : null}
            </span>
            <span>{uploadPercent !== null ? 'Subiendo…' : busy ? 'Traduciendo…' : 'Traducir video'}</span>
          </button>
        </div>
        {submitError && <p className="text-sm px-1" style={{ color: 'var(--color-error)' }}>{submitError}</p>}

        <StageProgress job={job} uploadPercent={uploadPercent} />
      </section>

      <div className="grid gap-6 items-start grid-cols-1 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.5fr)]">
        <section className="flex flex-col gap-3 min-w-0" aria-label="Historial de traducciones">
          <h2 className="text-white text-sm font-semibold">Historial de traducciones</h2>
          {history.length === 0 ? (
            <p className="text-muted text-sm">Aún no tienes traducciones.</p>
          ) : (
            <div className="flex flex-col gap-3 max-h-[480px] overflow-y-auto">
              {history.map((item) => (
                <HistoryRow
                  key={item.id}
                  job={item}
                  selected={item.id === activeJobId}
                  onSelect={() => setActiveJobId(item.id)}
                />
              ))}
            </div>
          )}
        </section>

        <section className="flex flex-col gap-3 min-w-0" aria-label="Resultado">
          <h2 className="text-white text-sm font-semibold">Resultado</h2>
          {job?.status === 'completed' ? (
            <ResultPanel job={job} />
          ) : (
            <div className="rounded-lg px-4 py-8 text-center" style={{ background: 'var(--bg-card-hover)' }}>
              <p className="text-muted text-sm">
                {loading
                  ? 'Cargando…'
                  : job && ['queued', 'processing'].includes(job.status)
                    ? 'El video aparecerá aquí cuando termine la traducción.'
                    : job?.status === 'failed'
                      ? 'Esta traducción no se completó.'
                      : 'Sube un video o selecciona una traducción del historial.'}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
