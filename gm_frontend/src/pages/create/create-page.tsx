// ─────────────────────────────────────────────────────────────────────────────
// src/pages/create/create-page.tsx
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useRef, useState } from 'react'
import {
  generateSong,
  getSongJob,
  getSongPlayUrl,
  getSongThumbnailUrl,
} from '../../api/modules/songs.api'
import type { JobStatus } from '../../api/modules/songs.api'
import styles from './create-page.module.css'
import StyleSelectorsPreview, {
  ConfigurationSelect,
} from '../../components/create/style-selectors-preview'
import { isAxiosError } from 'axios'
import { useAuthStore } from '../../store/auth.store'

// ── Constantes ────────────────────────────────────────────────────────────────

const POLLING_INTERVAL_MS = 5_000

type Mode = 'description' | 'exact_lyrics' | 'auto_lyrics'
type VocalType = 'male' | 'female' | 'auto'
type Language = 'es' | 'en'

const VOCAL_OPTIONS: { id: VocalType; label: string; icon: string }[] = [
  { id: 'female', label: 'Femenina', icon: '♀' },
  { id: 'male', label: 'Masculina', icon: '♂' },
  { id: 'auto', label: 'Auto', icon: '✦' },
]

const LANGUAGE_OPTIONS: { id: Language; label: string }[] = [
  { id: 'es', label: 'Español' },
  { id: 'en', label: 'English' },
]

const MODES: { id: Mode; label: string; hint: string; icon: string }[] = [
  {
    id: 'description',
    label: 'Descripción',
    hint: 'Describe la idea; la IA crea letra y música.',
    icon: '✦',
  },
  {
    id: 'exact_lyrics',
    label: 'Letra exacta',
    hint: 'Usa tu letra; la IA crea la música.',
    icon: '≡',
  },
  {
    id: 'auto_lyrics',
    label: 'Letra IA',
    hint: 'Describe la historia; la IA escribe la letra.',
    icon: '✎',
  },
]

interface DurationOption {
  label: string
  value: number
}
const DURATION_OPTIONS: DurationOption[] = [
  { label: '30-40 seg', value: 40.0 },
  { label: '1 min', value: 60.0 },
  { label: '2:30+ min', value: 150.0 },
]

type GenerationStage = 'idle' | 'submitting' | 'polling' | 'ready' | 'no_credits' | 'error'

const STAGE_LABELS: Record<GenerationStage, string> = {
  idle: '',
  submitting: 'Preparando tu canción...',
  polling: 'Creando tu canción...',
  ready: '¡Tu canción está lista!',
  no_credits: 'Sin créditos',
  error: 'No pudimos crearla',
}

interface ReadySong {
  songId: string
  playUrl: string
  thumbnailUrl: string
}

// ── Componente ────────────────────────────────────────────────────────────────

export default function CreatePage() {
  const [mode, setMode] = useState<Mode>('description')
  const [duration, setDuration] = useState<number>(40.0)
  const [vocalType, setVocalType] = useState<VocalType>('auto')
  const [language, setLanguage] = useState<Language>('es')

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [prompt, setPrompt] = useState('')
  const [lyrics, setLyrics] = useState('')
  const [describedLyrics, setDescribedLyrics] = useState('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])

  const [stage, setStage] = useState<GenerationStage>('idle')
  const [ready, setReady] = useState<ReadySong | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  useEffect(() => () => stopPolling(), [])

  // ── Polling ────────────────────────────────────────────────
  function startPolling(jobId: string, songId: string) {
    setStage('polling')
    pollingRef.current = setInterval(async () => {
      try {
        const job = await getSongJob(jobId)
        await handleJobStatus(job.status, songId)
      } catch {
        stopPolling()
        setStage('error')
        setErrorMsg('Error al consultar el estado del trabajo.')
      }
    }, POLLING_INTERVAL_MS)
  }

  function stopPolling() {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }

  async function handleJobStatus(status: JobStatus, songId: string) {
    if (status === 'no_credits') {
      stopPolling()
      setStage('no_credits')
      return
    }
    if (status === 'ready') {
      stopPolling()
      try {
        const [playUrl, thumbnailUrl] = await Promise.all([
          getSongPlayUrl(songId),
          getSongThumbnailUrl(songId),
        ])
        setReady({ songId, playUrl, thumbnailUrl })
        setStage('ready')
      } catch {
        setStage('error')
        setErrorMsg('La canción está lista pero no se pudo cargar el audio.')
      }
      return
    }
    if (status === 'error') {
      stopPolling()
      setStage('error')
      setErrorMsg('El servidor reportó un error al generar la canción.')
    }
  }

  // ── Validación ────────────────────────────────────────────
  function validate(): string | null {
    if (!title.trim()) {
      return 'El título es obligatorio.'
    }
    if (mode === 'description' && !description.trim()) {
      return 'Describe qué quieres escuchar en tu canción.'
    }
    if (mode === 'exact_lyrics') {
      if (!prompt.trim() && selectedTags.length === 0) {
        return 'Especifica el estilo musical o selecciona una opción.'
      }
      if (!lyrics.trim()) {
        return 'Escribe la letra exacta de la canción.'
      }
    }
    if (mode === 'auto_lyrics') {
      if (!prompt.trim() && selectedTags.length === 0) {
        return 'Especifica el estilo musical o selecciona una opción.'
      }
      if (!describedLyrics.trim()) {
        return 'Describe de qué trata la canción.'
      }
    }
    return null
  }

  // ── Payload — los tags seleccionados se combinan con los campos ────────────
  function buildPayload(): Record<string, unknown> {
    const tagsStr = selectedTags.join(', ')

    const base = {
      title: title.trim(),
      audio_duration: duration,
      instrumental: false,
      vocal_type: vocalType,
      language,
    }

    if (mode === 'description') {
      // Tags se anteponen a la descripción: "lofi, chill, slow. [descripción del usuario]"
      const fullDesc = tagsStr ? `${tagsStr}. ${description.trim()}`.trim() : description.trim()
      return { ...base, description: fullDesc }
    }

    // Para modos de letra, los tags van al campo prompt (estilo musical)
    const fullPrompt =
      tagsStr && prompt.trim() ? `${tagsStr}, ${prompt.trim()}` : tagsStr || prompt.trim()

    if (mode === 'exact_lyrics') {
      return { ...base, prompt: fullPrompt, lyrics: lyrics.trim() }
    }
    return { ...base, prompt: fullPrompt, described_lyrics: describedLyrics.trim() }
  }

  // ── Submit ────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const validationError = validate()
    if (validationError) {
      setErrorMsg(validationError)
      return
    }

    setErrorMsg(null)
    setReady(null)
    setStage('submitting')

    try {
      const payload = buildPayload()
      const res = await generateSong(payload as Parameters<typeof generateSong>[0])

      import('../../api/auth-service').then(({ authService }) => {
        authService
          .getProfile()
          .then((profile) => {
            useAuthStore.getState().setUser(profile)
          })
          .catch(console.error)
      })

      const firstCheck = await getSongJob(res.job_id)
      if (firstCheck.status === 'ready') {
        await handleJobStatus('ready', res.song_id)
      } else if (firstCheck.status === 'no_credits') {
        setStage('no_credits')
      } else {
        startPolling(res.job_id, res.song_id)
      }
    } catch (err: unknown) {
      if (isAxiosError(err) && err.response?.status === 402) {
        setStage('no_credits')
      } else {
        setStage('error')
        setErrorMsg('No se pudo iniciar la generación. Intenta de nuevo.')
      }
    }
  }

  function handleReset() {
    stopPolling()
    setStage('idle')
    setReady(null)
    setErrorMsg(null)
    setTitle('')
    setDescription('')
    setPrompt('')
    setLyrics('')
    setDescribedLyrics('')
    setSelectedTags([])
    setVocalType('auto')
    setLanguage('es') // default español
  }

  function handleModeChange(m: Mode) {
    setMode(m)
    setErrorMsg(null)
    setSelectedTags([])
  }

  const isBusy = stage === 'submitting' || stage === 'polling'
  const { user } = useAuthStore()
  const selectedMode = MODES.find((item) => item.id === mode)
  const selectedDuration = DURATION_OPTIONS.find((item) => item.value === duration)
  const selectedVocal = VOCAL_OPTIONS.find((item) => item.id === vocalType)
  const selectedLanguage = LANGUAGE_OPTIONS.find((item) => item.id === language)

  return (
    <div className={styles.page}>
      <div className={styles.inner}>
        {/* ── Header ──────────────────────────────────────────── */}
        <div className={styles.header}>
          <div className="flex items-center justify-between gap-4">
            <h1 className={styles.pageTitle}>Crear canción</h1>
          </div>
          <p className={styles.pageSubtitle}>Define la idea, el estilo y la voz.</p>
        </div>

        <div className={styles.workspace}>
          <form id="create-song-form" onSubmit={handleSubmit} className={styles.form} noValidate>
            {/* ── Tabs de modo ──────────────────────────────────── */}
            <div className={styles.sectionHeading}>
              <span className={styles.sectionNumber}>01</span>
              <div>
                <strong>Idea y estilo</strong>
                <span>Elige cómo crear tu canción.</span>
              </div>
            </div>
            <div className={styles.tabs} role="tablist" aria-label="Modo de creación">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  role="tab"
                  aria-selected={mode === m.id}
                  disabled={isBusy}
                  onClick={() => handleModeChange(m.id)}
                  className={`${styles.tab} ${mode === m.id ? styles.tabActive : ''}`}
                >
                  <span className={styles.tabIcon} aria-hidden="true">
                    {m.icon}
                  </span>
                  <span className={styles.tabLabel}>{m.label}</span>
                  <span className={styles.tabHint}>{m.hint}</span>
                </button>
              ))}
            </div>
            {/* ── Título ────────────────────────────────────────── */}
            <div className={styles.fieldGroup}>
              <label htmlFor="title" className={styles.label}>
                Título
              </label>
              <input
                id="title"
                type="text"
                placeholder="Ej. Ecos de medianoche"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={isBusy}
                className={styles.input}
              />
            </div>

            {/* ── Modo Descripción ──────────────────────────────── */}
            {mode === 'description' && (
              <div className={styles.fieldGroup}>
                <label htmlFor="description" className={styles.label}>
                  Describe tu canción
                  <span className={styles.labelHint}>Cuenta la escena, emoción o historia.</span>
                </label>
                <StyleSelectorsPreview
                  selected={selectedTags}
                  onChange={setSelectedTags}
                  disabled={isBusy}
                />
                <textarea
                  id="description"
                  placeholder="Ej. Un viaje nocturno entre soledad y esperanza..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={isBusy}
                  rows={5}
                  className={styles.textarea}
                />
              </div>
            )}

            {/* ── Modos con letra: campo Estilo ──────────────────── */}
            {(mode === 'exact_lyrics' || mode === 'auto_lyrics') && (
              <div className={styles.fieldGroup}>
                <label htmlFor="prompt" className={styles.label}>
                  Estilo musical
                  <span className={styles.labelHint}>Combina estilos e instrumentos.</span>
                </label>
                <StyleSelectorsPreview
                  selected={selectedTags}
                  onChange={setSelectedTags}
                  disabled={isBusy}
                />
                <input
                  id="prompt"
                  type="text"
                  placeholder="Ej. Synthwave oscuro con sintetizadores..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={isBusy}
                  className={styles.input}
                />
              </div>
            )}

            {/* ── Letra exacta ──────────────────────────────────── */}
            {mode === 'exact_lyrics' && (
              <div className={styles.fieldGroup}>
                <label htmlFor="lyrics" className={styles.label}>
                  Tu letra
                  <span className={styles.labelHint}>La música se adapta a esta letra.</span>
                </label>
                <textarea
                  id="lyrics"
                  placeholder={'Escribe aquí la letra completa...'}
                  value={lyrics}
                  onChange={(e) => setLyrics(e.target.value)}
                  disabled={isBusy}
                  rows={7}
                  className={styles.textarea}
                />
              </div>
            )}

            {/* ── Letra automática ──────────────────────────────── */}
            {mode === 'auto_lyrics' && (
              <div className={styles.fieldGroup}>
                <label htmlFor="described_lyrics" className={styles.label}>
                  Idea para la letra
                  <span className={styles.labelHint}>Tema, historia o mensaje.</span>
                </label>
                <textarea
                  id="described_lyrics"
                  placeholder="Ej. Dos personas se separan, pero esperan reencontrarse..."
                  value={describedLyrics}
                  onChange={(e) => setDescribedLyrics(e.target.value)}
                  disabled={isBusy}
                  rows={5}
                  className={styles.textarea}
                />
              </div>
            )}

            {/* ── Duración ──────────────────────────────────────── */}
            <div className={styles.sectionHeading}>
              <span className={styles.sectionNumber}>02</span>
              <div>
                <strong>Ajustes de generación</strong>
                <span>Elige duración, voz e idioma.</span>
              </div>
            </div>
            <div className={styles.settingsSection}>
              <div className={styles.fieldGroup}>
                <ConfigurationSelect
                  label="Duración"
                  value={String(duration)}
                  options={DURATION_OPTIONS.map((option) => ({
                    value: String(option.value),
                    label: option.label,
                  }))}
                  onChange={(value) => setDuration(Number(value))}
                  disabled={isBusy}
                />
              </div>

              <div className={styles.settingsGrid}>
                <div className={styles.fieldGroup}>
                  <ConfigurationSelect
                    label="Tipo de voz"
                    value={vocalType}
                    options={VOCAL_OPTIONS.map((option) => ({
                      value: option.id,
                      label: `${option.icon} ${option.label}`,
                    }))}
                    onChange={(value) => setVocalType(value as VocalType)}
                    disabled={isBusy}
                  />
                </div>

                <div className={styles.fieldGroup}>
                  <ConfigurationSelect
                    label="Idioma"
                    value={language}
                    options={LANGUAGE_OPTIONS.map((option) => ({
                      value: option.id,
                      label: option.label,
                    }))}
                    onChange={(value) => setLanguage(value as Language)}
                    disabled={isBusy}
                  />
                </div>
              </div>
            </div>

            {/* ── Error de validación ───────────────────────────── */}
            {errorMsg && stage === 'idle' && (
              <p className={styles.validationMsg} role="alert">
                {errorMsg}
              </p>
            )}
          </form>

          <aside className={styles.summary} aria-label="Resumen de creación">
            <div className={styles.summaryHeader}>
              <div>
                <span className={styles.summaryEyebrow}>Vista previa</span>
                <h2 className={styles.summaryTitle}>{title || 'Tu nueva canción'}</h2>
              </div>
              <div className={styles.summaryCredits}>
                <span>Créditos</span>
                <strong>{user?.credit_balance ?? 0}</strong>
              </div>
            </div>

            <div className={styles.summaryDetails}>
              <div>
                <span>Modo</span>
                <strong>{selectedMode?.label}</strong>
              </div>
              <div>
                <span>Duración</span>
                <strong>{selectedDuration?.label}</strong>
              </div>
              <div>
                <span>Voz e idioma</span>
                <strong>
                  {selectedVocal?.label} · {selectedLanguage?.label}
                </strong>
              </div>
              <div>
                <span>Estilo</span>
                <strong>
                  {selectedTags.length ? `${selectedTags.length} seleccionados` : 'Sin estilos'}
                </strong>
              </div>
            </div>

            {stage === 'idle' && (
              <p className={styles.summaryHint}>Aquí aparecerán los ajustes de tu canción.</p>
            )}

            <button
              type="submit"
              form="create-song-form"
              disabled={isBusy}
              className={styles.submitBtn}
            >
              {isBusy ? <span className={styles.spinner} aria-hidden="true" /> : '✦'}
              {isBusy ? 'Creando tu canción...' : 'Crear canción'}
            </button>

            {stage !== 'idle' && (
              <div
                className={`${styles.statusCard} ${
                  stage === 'no_credits' || stage === 'error'
                    ? styles.statusError
                    : stage === 'ready'
                      ? styles.statusSuccess
                      : styles.statusLoading
                }`}
              >
                {isBusy && <span className={styles.spinnerLarge} />}
                {stage === 'ready' && <span className={styles.statusIcon}>✓</span>}
                {(stage === 'no_credits' || stage === 'error') && (
                  <span className={styles.statusIcon}>!</span>
                )}
                <div className={styles.statusText}>
                  <strong>{STAGE_LABELS[stage]}</strong>
                  {stage === 'no_credits' && <span>Necesitas más créditos para crearla.</span>}
                  {stage === 'error' && errorMsg && <span>{errorMsg}</span>}
                  {stage === 'polling' && (
                    <span>Puedes seguir navegando; te avisaremos cuando esté lista.</span>
                  )}
                </div>
                {isBusy && (
                  <div className={styles.statusProgress} aria-label="Progreso de generación">
                    <span className={stage === 'submitting' ? styles.progressSubmitting : ''} />
                  </div>
                )}
                {(stage === 'ready' || stage === 'no_credits' || stage === 'error') && (
                  <button onClick={handleReset} className={styles.resetBtn}>
                    Nueva canción
                  </button>
                )}
              </div>
            )}

            {stage === 'ready' && ready && (
              <div className={styles.resultCard}>
                {ready.thumbnailUrl && (
                  <img src={ready.thumbnailUrl} alt="Portada" className={styles.thumbnail} />
                )}
                <div className={styles.resultInfo}>
                  <p className={styles.resultLabel}>{title || 'Tu canción está lista'}</p>
                  <audio
                    key={ready.playUrl}
                    src={ready.playUrl}
                    controls
                    autoPlay
                    className={styles.audioPlayer}
                  />
                  <p className={styles.resultHint}>
                    Guardada en{' '}
                    <a href="/library" className={styles.resultLink}>
                      Tu biblioteca
                    </a>
                    .
                  </p>
                </div>
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  )
}
