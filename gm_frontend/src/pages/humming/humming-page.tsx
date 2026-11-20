import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Check,
  Download,
  FileMusic,
  LoaderCircle,
  Mic,
  Pause,
  Play,
  RotateCcw,
  Square,
  Upload,
} from 'lucide-react'

import {
  chooseHummingVersion,
  getHummingErrorMessage,
  getHummingJobs,
  isNoCreditsError,
  uploadHumming,
} from '../../api/modules/humming.api'
import type { HummingJob, HummingVersion } from '../../api/modules/humming.api'
import { useAudioRecorder } from '../../hooks/useAudioRecorder'
import { useHummingJob } from '../../hooks/useHummingJob'
import { useGlobalAudioPlayer } from '../../components/player/use-global-audio-player'
import { useAuthStore } from '../../store/auth.store'
import EnhancePanel from '../../components/humming/enhance-panel'
import MelodyChart from '../../components/humming/melody-chart'
import SimilarityBadge, { SIMILARITY_EXPLANATION } from '../../components/humming/similarity-badge'
import InspirationPanel from '../../components/humming/inspiration-panel'
import styles from './humming-page.module.css'

// Límites del worker de tarareo (gm_tarareo): 8 a 30 s de sonido útil.
const MIN_SECONDS = 8
const MAX_SECONDS = 30
// Coincide con HUMMING_CREDIT_COST del backend (valor por defecto).
const CREDIT_COST = 1

const STYLE_LABELS: Record<string, string> = {
  pop: 'Pop',
  folk: 'Folk',
  balada: 'Balada',
  lofi: 'Lo-fi',
  rock_suave: 'Rock suave',
  epico: 'Épico',
  electronico: 'Electrónico',
}

const STAGE_LABELS: Record<string, string> = {
  ingesta: 'Preparando tu grabación…',
  preprocesado: 'Limpiando el audio…',
  melodia: 'Detectando tu melodía…',
  limpieza: 'Afinando las notas…',
  analisis: 'Analizando ritmo y tonalidad…',
  armonia: 'Armando los acordes…',
  estilo: 'Eligiendo el estilo…',
  arreglo: 'Arreglando los instrumentos…',
  render: 'Grabando la versión principal…',
  'version-1-lista': 'Versión principal lista…',
  'alternativa-2': 'Creando una versión alternativa…',
  'version-2-lista': 'Segunda versión lista…',
  'alternativa-3': 'Creando otra versión alternativa…',
  'version-3-lista': 'Tercera versión lista…',
  subida: 'Guardando tus canciones…',
  completado: 'Listo',
}

const STATUS_LABELS: Record<string, string> = {
  queued: 'En cola',
  processing: 'Procesando',
  completed: 'Listo',
  failed: 'Error',
}

function styleLabel(style: string | null | undefined) {
  if (!style) {
    return 'Versión'
  }
  return STYLE_LABELS[style] ?? style
}

function formatSeconds(seconds: number) {
  const whole = Math.floor(seconds)
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`
}

function refreshCredits() {
  import('../../api/auth-service').then(({ authService }) => {
    authService
      .getProfile()
      .then((profile) => useAuthStore.getState().setUser(profile))
      .catch(console.error)
  })
}

// ── Grabadora ───────────────────────────────────────────────────────────────

interface RecorderCardProps {
  busy: boolean
  onSubmit: (file: File, title: string) => Promise<boolean>
  submitError: string | null
  noCredits: boolean
}

function RecorderCard({ busy, onSubmit, submitError, noCredits }: RecorderCardProps) {
  const recorder = useAudioRecorder(MAX_SECONDS)
  const [uploaded, setUploaded] = useState<File | null>(null)
  const [uploadedUrl, setUploadedUrl] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [sending, setSending] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(
    () => () => {
      if (uploadedUrl) {
        URL.revokeObjectURL(uploadedUrl)
      }
    },
    [uploadedUrl]
  )

  const isRecording = recorder.state === 'recording'
  const source = uploaded ?? recorder.recording?.file ?? null
  const previewUrl = uploadedUrl ?? recorder.recording?.url ?? null
  const tooShort =
    !uploaded && recorder.recording !== null && recorder.recording.seconds < MIN_SECONDS
  const canSubmit = Boolean(source) && !tooShort && !busy && !sending && !isRecording

  function clearUpload() {
    setUploaded(null)
    setUploadedUrl(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  async function handleRecordClick() {
    if (isRecording) {
      recorder.stop()
      return
    }
    clearUpload()
    await recorder.start()
  }

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    recorder.reset()
    setUploaded(file)
    setUploadedUrl(URL.createObjectURL(file))
  }

  async function handleSubmit() {
    if (!source || !canSubmit) {
      return
    }
    setSending(true)
    const ok = await onSubmit(source, title)
    setSending(false)
    if (ok) {
      recorder.reset()
      clearUpload()
      setTitle('')
    }
  }

  const progressPct = Math.min(100, (recorder.elapsed / MAX_SECONDS) * 100)

  return (
    <section
      className="rounded-xl p-6 flex flex-col gap-5"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      aria-labelledby="humming-recorder-title"
    >
      <div className="flex items-center gap-5">
        <button
          type="button"
          onClick={handleRecordClick}
          disabled={busy || sending || recorder.state === 'requesting'}
          className={`${styles.recordButton} ${isRecording ? styles.recording : ''}`}
          aria-label={isRecording ? 'Detener grabación' : 'Empezar a grabar'}
        >
          {recorder.state === 'requesting' ? (
            <LoaderCircle size={32} className="animate-spin" aria-hidden="true" />
          ) : isRecording ? (
            <Square size={28} fill="currentColor" aria-hidden="true" />
          ) : (
            <Mic size={34} aria-hidden="true" />
          )}
        </button>

        <div className="flex-1 min-w-0 flex flex-col gap-2">
          <h2 id="humming-recorder-title" className="text-white text-lg font-semibold">
            {isRecording ? 'Grabando… tararea tu melodía' : 'Graba tu tarareo'}
          </h2>
          <div className={styles.meter} aria-hidden="true">
            <div className={styles.meterFill} style={{ width: `${progressPct}%` }} />
            <div
              className={styles.meterMin}
              style={{ left: `${(MIN_SECONDS / MAX_SECONDS) * 100}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted">
            <span aria-live="polite">
              {formatSeconds(recorder.elapsed)} / {formatSeconds(MAX_SECONDS)}
            </span>
            <span>Mínimo {MIN_SECONDS} s · ideal 15–20 s</span>
          </div>
        </div>
      </div>

      <p className="text-muted text-sm">
        Tararea con «na-na» o «la-la» en un lugar tranquilo. Nosotros detectamos la melodía, el
        ritmo y la tonalidad, y la convertimos en canciones en distintos estilos.
      </p>

      <InspirationPanel
        disabled={busy || sending || isRecording}
        onRecord={() => {
          if (!isRecording) {
            handleRecordClick()
          }
        }}
      />

      {previewUrl && (
        <div className="flex flex-col gap-2">
          <p className="text-white text-sm font-medium">
            {uploaded
              ? uploaded.name
              : `Tu grabación (${formatSeconds(recorder.recording?.seconds ?? 0)})`}
          </p>
          <audio controls src={previewUrl} className="w-full" />
          {tooShort && (
            <p className="text-sm" style={{ color: 'var(--color-warning)' }}>
              La grabación es muy corta: graba al menos {MIN_SECONDS} segundos.
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.webm,.ogg,.m4a,.mp4,.mp3,.wav,.aac,.flac"
          onChange={handleFile}
          className="sr-only"
          id="humming-file"
          disabled={busy || isRecording}
        />
        <label
          htmlFor="humming-file"
          className="inline-flex items-center gap-2 text-sm text-muted hover:text-white cursor-pointer"
        >
          <Upload size={16} aria-hidden="true" />o sube un archivo de audio
        </label>
        {(recorder.recording || uploaded) && (
          <button
            type="button"
            onClick={() => {
              recorder.reset()
              clearUpload()
            }}
            className="inline-flex items-center gap-2 text-sm text-muted hover:text-white"
          >
            <RotateCcw size={16} aria-hidden="true" />
            Descartar
          </button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <label className="sr-only" htmlFor="humming-title">
          Título (opcional)
        </label>
        <input
          id="humming-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={200}
          placeholder="Título (opcional)"
          className="flex-1 rounded-lg px-4 py-2.5 text-sm text-white outline-none"
          style={{ background: 'var(--bg-card-hover)', border: '1px solid var(--border-strong)' }}
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-pill px-6 py-2.5 text-sm font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ background: 'var(--color-primary)', color: 'var(--color-on-primary)' }}
        >
          {sending && <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />}
          Crear canciones · {CREDIT_COST} crédito{CREDIT_COST === 1 ? '' : 's'}
        </button>
      </div>

      {(recorder.error || submitError) && (
        <p className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
          {recorder.error ?? submitError}{' '}
          {noCredits && (
            <Link to="/payments" className="underline">
              Recargar créditos
            </Link>
          )}
        </p>
      )}
    </section>
  )
}

// ── Resultado ───────────────────────────────────────────────────────────────

interface VersionCardProps {
  job: HummingJob
  version: HummingVersion
  playing: boolean
  choosing: boolean
  onPlay: () => void
  onChoose: () => void
}

function VersionCard({ job, version, playing, choosing, onPlay, onChoose }: VersionCardProps) {
  const chosen = job.chosen_version === version.number
  const ai = version.ai
  const aiPending = Boolean(ai && (ai.status === 'queued' || ai.status === 'processing'))
  const aiFailed = ai?.status === 'failed'
  // Se escucha apenas está; se elige cuando terminan el tarareo y su versión con IA.
  const locked = (job.chosen_version !== null && !chosen) || job.status !== 'completed' || aiPending

  return (
    <article
      className="rounded-lg p-4 flex flex-col gap-3"
      style={{
        background: 'var(--bg-card-hover)',
        border: `1px solid ${chosen ? 'var(--color-primary)' : 'transparent'}`,
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex items-center gap-3">
          {ai?.cover_url && (
            <img src={ai.cover_url} alt="" className="w-10 h-10 rounded-md object-cover shrink-0" />
          )}
          <div className="min-w-0">
            <h3 className="text-white font-semibold">{styleLabel(version.style)}</h3>
            <p className="text-muted text-xs">
              Versión {version.number}
              {ai?.status === 'completed' && ' · producida con IA'}
            </p>
            {ai?.status === 'completed' && ai.similarity && (
              <SimilarityBadge similarity={ai.similarity} />
            )}
          </div>
        </div>
        {version.number === 1 && (
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full shrink-0"
            style={{ background: 'var(--color-primary-soft)', color: 'var(--color-primary)' }}
          >
            Principal
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPlay}
          disabled={aiPending}
          className="w-10 h-10 rounded-full inline-flex items-center justify-center shrink-0 disabled:opacity-60 disabled:cursor-wait"
          style={{ background: 'var(--color-primary)', color: 'var(--color-on-primary)' }}
          aria-label={
            playing
              ? `Pausar ${styleLabel(version.style)}`
              : `Escuchar ${styleLabel(version.style)}`
          }
        >
          {aiPending ? (
            <LoaderCircle size={18} className="animate-spin" aria-hidden="true" />
          ) : playing ? (
            <Pause size={18} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={18} fill="currentColor" aria-hidden="true" />
          )}
        </button>

        {aiPending ? (
          <span className="text-xs text-muted">Mejorando con IA…</span>
        ) : chosen ? (
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-success">
            <Check size={16} aria-hidden="true" /> En tu biblioteca
          </span>
        ) : (
          <button
            type="button"
            onClick={onChoose}
            disabled={locked || choosing}
            title={
              job.status !== 'completed'
                ? 'Podrás elegir cuando terminen todas las versiones'
                : undefined
            }
            className="rounded-pill px-4 py-2 text-sm font-medium text-white disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
            style={{ border: '1px solid var(--border-strong)' }}
          >
            {choosing ? (
              <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
            ) : (
              <Check size={14} aria-hidden="true" />
            )}
            Elegir
          </button>
        )}

        {version.midi_url && (
          <a
            href={version.midi_url}
            className="ml-auto text-muted hover:text-white inline-flex items-center gap-1 text-xs"
            title="Descargar MIDI"
          >
            <Download size={14} aria-hidden="true" /> MIDI
          </a>
        )}
      </div>
      {aiFailed && (
        <p className="text-xs text-muted">
          No se pudo producir con IA; se usa la versión original.
        </p>
      )}
    </article>
  )
}

interface ResultPanelProps {
  job: HummingJob
  onChosen: () => void
  onEnhanceRequested: () => void
  refresh: () => Promise<HummingJob | null>
}

function ResultPanel({ job, onChosen, onEnhanceRequested, refresh }: ResultPanelProps) {
  const { track, isPlaying, playTrack, pause } = useGlobalAudioPlayer()
  const [choosing, setChoosing] = useState<number | null>(null)
  const [chooseError, setChooseError] = useState<string | null>(null)

  const working = job.status === 'queued' || job.status === 'processing'

  // Sin versiones todavía: solo el progreso.
  if (working && job.versions.length === 0) {
    const label = STAGE_LABELS[job.stage] ?? (job.status === 'queued' ? 'En cola…' : 'Procesando…')
    return (
      <div className="flex flex-col gap-3" aria-live="polite">
        <div className="flex items-center justify-between">
          <span className="text-white text-sm font-medium inline-flex items-center gap-2">
            <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
            {label}
          </span>
          <span className="text-xs text-muted">{job.progress}%</span>
        </div>
        <div className={styles.meter}>
          <div className={styles.meterFill} style={{ width: `${job.progress}%` }} />
        </div>
        <p className="text-muted text-xs">Suele tardar menos de un minuto.</p>
      </div>
    )
  }

  if (job.status === 'failed') {
    return (
      <div
        className="rounded-lg px-4 py-4 flex flex-col gap-1"
        role="alert"
        style={{
          background: 'var(--color-error-soft)',
          border: '1px solid var(--color-error-border)',
        }}
      >
        <p className="text-white text-sm font-semibold">
          No pudimos crear canciones con este tarareo
        </p>
        <p className="text-sm" style={{ color: 'var(--text-base-soft)' }}>
          {job.error_message ?? 'Intenta grabarlo de nuevo.'}
        </p>
        <p className="text-xs text-muted">No se descontaron créditos.</p>
      </div>
    )
  }

  async function handlePlay(version: HummingVersion) {
    const trackId = `humming:${job.id}:${version.number}`
    if (track?.id === trackId && isPlaying) {
      pause()
      return
    }
    // Las URLs firmadas vencen: se piden de nuevo justo antes de reproducir.
    const fresh = await refresh().catch(() => null)
    const latest = fresh?.versions.find((item) => item.number === version.number) ?? version
    const conIa = latest.ai?.status === 'completed' && latest.ai.audio_url
    playTrack({
      id: trackId,
      audioUrl: conIa ? (latest.ai?.audio_url as string) : latest.audio_url,
      title: job.title || 'Tu tarareo',
      subtitle: `${styleLabel(version.style)}${conIa ? ' · producida con IA' : ''}`,
      coverUrl: conIa ? latest.ai?.cover_url : null,
    })
  }

  async function handleChoose(version: HummingVersion) {
    setChoosing(version.number)
    setChooseError(null)
    try {
      await chooseHummingVersion(job.id, version.number, job.title)
      await refresh()
      onChosen()
    } catch (error) {
      setChooseError(getHummingErrorMessage(error, 'No se pudo guardar la versión.'))
    } finally {
      setChoosing(null)
    }
  }

  const meta = job.metadata
  const conIa = job.versions.filter((v) => v.ai)
  const aiTotal = conIa.length
  const aiListas = conIa.filter(
    (v) => v.ai?.status === 'completed' || v.ai?.status === 'failed'
  ).length
  const aiWorking = conIa.some((v) => v.ai?.status === 'queued' || v.ai?.status === 'processing')
  // La mitad del avance es el tarareo (worker) y la otra mitad la producción con IA.
  const progresoTotal = aiTotal
    ? Math.round(job.progress / 2 + (50 * aiListas) / Math.max(aiTotal, job.versions.length))
    : job.progress

  return (
    <div className="flex flex-col gap-5">
      {(working || aiWorking) && (
        <div className="flex flex-col gap-2" aria-live="polite">
          <div className="flex items-center justify-between">
            <span className="text-white text-sm font-medium inline-flex items-center gap-2">
              <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
              {aiListas > 0
                ? 'Escucha las que ya están mientras producimos las demás con IA…'
                : 'Produciendo tus versiones con IA…'}
            </span>
            <span className="text-xs text-muted">
              {aiTotal > 0
                ? `${aiListas}/${Math.max(aiTotal, job.versions.length)} con IA`
                : `${job.progress}%`}
            </span>
          </div>
          <div className={styles.meter}>
            <div className={styles.meterFill} style={{ width: `${progresoTotal}%` }} />
          </div>
        </div>
      )}
      <div className="flex flex-col gap-2">
        {meta.estiloMensaje && <p className="text-white font-medium">{meta.estiloMensaje}</p>}
        <dl className="flex flex-wrap gap-2 text-xs">
          {meta.bpm !== undefined && (
            <div className="rounded-full px-3 py-1" style={{ background: 'var(--bg-card-hover)' }}>
              <dt className="sr-only">Tempo</dt>
              <dd className="text-white">{Math.round(meta.bpm)} BPM</dd>
            </div>
          )}
          {meta.tonalidad && (
            <div className="rounded-full px-3 py-1" style={{ background: 'var(--bg-card-hover)' }}>
              <dt className="sr-only">Tonalidad</dt>
              <dd className="text-white">{meta.tonalidad}</dd>
            </div>
          )}
          {meta.acordes && meta.acordes.length > 0 && (
            <div className="rounded-full px-3 py-1" style={{ background: 'var(--bg-card-hover)' }}>
              <dt className="sr-only">Acordes</dt>
              <dd className="text-white">{meta.acordes.join(' · ')}</dd>
            </div>
          )}
        </dl>
      </div>

      {meta.grafico && <MelodyChart chart={meta.grafico} />}

      <div className={styles.versionsGrid}>
        {job.versions.map((version) => (
          <VersionCard
            key={version.number}
            job={job}
            version={version}
            playing={track?.id === `humming:${job.id}:${version.number}` && isPlaying}
            choosing={choosing === version.number}
            onPlay={() => handlePlay(version)}
            onChoose={() => handleChoose(version)}
          />
        ))}
      </div>

      {job.versions.some((v) => v.ai?.similarity) && (
        <p className="text-xs text-muted">
          <span className="text-white">Parecido con tu melodía:</span> {SIMILARITY_EXPLANATION}
        </p>
      )}

      {chooseError && (
        <p className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
          {chooseError}
        </p>
      )}

      {job.song_id ? (
        <p className="text-sm text-muted">
          Guardamos tu versión elegida.{' '}
          <Link to="/library" className="text-white underline">
            Ver en la biblioteca
          </Link>
        </p>
      ) : (
        <p className="text-sm text-muted">
          Escucha las versiones y elige la que más te guste para guardarla en tu biblioteca.
        </p>
      )}

      {(job.downloads.score_musicxml_url || job.downloads.melody_midi_url) && (
        <div className="flex flex-wrap gap-4 text-sm">
          {job.downloads.score_musicxml_url && (
            <a
              href={job.downloads.score_musicxml_url}
              className="inline-flex items-center gap-1.5 text-muted hover:text-white"
            >
              <FileMusic size={16} aria-hidden="true" /> Partitura (MusicXML)
            </a>
          )}
          {job.downloads.melody_midi_url && (
            <a
              href={job.downloads.melody_midi_url}
              className="inline-flex items-center gap-1.5 text-muted hover:text-white"
            >
              <Download size={16} aria-hidden="true" /> Melodía (MIDI)
            </a>
          )}
        </div>
      )}

      {job.status === 'completed' && (
        <EnhancePanel
          job={job}
          refresh={refresh}
          onRequested={onEnhanceRequested}
          versionLabel={(number) => {
            const version = job.versions.find((item) => item.number === number)
            return `${number} (${styleLabel(version?.style)})`
          }}
        />
      )}
    </div>
  )
}

// ── Página ──────────────────────────────────────────────────────────────────

export default function HummingPage() {
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [noCredits, setNoCredits] = useState(false)
  const recoveredRef = useRef(false)

  const { job, loading, refresh, resume } = useHummingJob(activeJobId)
  const { data: history = [], refetch } = useQuery({
    queryKey: ['humming-jobs'],
    queryFn: getHummingJobs,
  })

  // Al entrar, mostrar el último tarareo (en curso o terminado).
  useEffect(() => {
    if (!recoveredRef.current && !activeJobId && history.length > 0) {
      recoveredRef.current = true
      setActiveJobId(history[0].id)
    }
  }, [activeJobId, history])

  // Mantener el historial al día cuando cambia el estado del tarareo activo.
  useEffect(() => {
    if (job?.status) {
      refetch()
    }
  }, [job?.status, refetch])

  // El cobro se confirma cuando el worker termina: actualizar el saldo visible.
  const finishedJobRef = useRef<string | null>(null)
  useEffect(() => {
    if (job?.status === 'completed' && finishedJobRef.current !== job.id) {
      finishedJobRef.current = job.id
      refreshCredits()
    }
  }, [job?.id, job?.status])

  // Cada mejora con IA terminada cobra créditos: actualizar el saldo.
  const finishedEnhancements = job?.enhancements.filter(
    (item) => item.status === 'completed'
  ).length
  useEffect(() => {
    if (finishedEnhancements) {
      refreshCredits()
    }
  }, [finishedEnhancements])

  const busy = Boolean(job && ['queued', 'processing'].includes(job.status))

  async function handleSubmit(file: File, title: string): Promise<boolean> {
    setSubmitError(null)
    setNoCredits(false)
    try {
      const created = await uploadHumming(file, title)
      recoveredRef.current = true
      setActiveJobId(created.id)
      refetch()
      refreshCredits()
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
    <div className="px-4 sm:px-8 pt-7 pb-20 flex flex-col gap-6">
      <header>
        <h1 className="text-white text-[32px] font-bold tracking-tight">Tararear</h1>
        <p className="text-muted text-sm mt-1">
          Tararea una melodía y conviértela en canciones instrumentales en distintos estilos.
        </p>
      </header>

      <div className="w-full max-w-2xl">
        <RecorderCard
          busy={busy}
          onSubmit={handleSubmit}
          submitError={submitError}
          noCredits={noCredits}
        />
      </div>

      <div className={styles.layout}>
        <section className="flex flex-col gap-3 min-w-0" aria-labelledby="humming-history-title">
          <h2 id="humming-history-title" className="text-white text-sm font-semibold">
            Tus tarareos
          </h2>
          {history.length === 0 ? (
            <p className="text-muted text-sm">Aún no tienes tarareos.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {history.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setActiveJobId(item.id)}
                    className="bg-card-hover rounded-lg px-4 py-3 flex items-center justify-between gap-3 w-full text-left"
                    style={{
                      border: `1px solid ${item.id === activeJobId ? 'var(--color-primary)' : 'transparent'}`,
                    }}
                    aria-current={item.id === activeJobId ? 'true' : undefined}
                  >
                    <div className="min-w-0">
                      <p className="text-white text-sm font-medium truncate">
                        {item.title ||
                          (item.metadata.estilo ? styleLabel(item.metadata.estilo) : 'Tarareo')}
                      </p>
                      <p className="text-muted text-xs">
                        {new Date(item.created_at).toLocaleString()}
                      </p>
                    </div>
                    <span
                      className="text-xs font-semibold px-2 py-1 rounded-full shrink-0"
                      style={{
                        background: 'var(--color-primary-soft)',
                        color:
                          item.status === 'failed'
                            ? 'var(--color-error)'
                            : item.status === 'completed'
                              ? 'var(--color-success)'
                              : 'var(--color-warning)',
                      }}
                    >
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-3 min-w-0" aria-labelledby="humming-result-title">
          <h2 id="humming-result-title" className="text-white text-sm font-semibold">
            Tus canciones
          </h2>
          <div
            className="rounded-xl p-5"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            {job ? (
              <ResultPanel
                job={job}
                refresh={refresh}
                onChosen={() => refetch()}
                onEnhanceRequested={() => {
                  resume()
                  refreshCredits()
                }}
              />
            ) : loading ? (
              <p className="text-muted text-sm inline-flex items-center gap-2">
                <LoaderCircle size={16} className="animate-spin" aria-hidden="true" /> Cargando…
              </p>
            ) : (
              <p className="text-muted text-sm">
                Graba tu primer tarareo para ver aquí las canciones.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
