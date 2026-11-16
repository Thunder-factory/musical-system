import { useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'
import type { ChangeEvent, DragEvent } from 'react'
import { getLibrary, getSongDetail } from '../../api/modules/songs.api'
import { getStemDownloadUrl, getStemJobs } from '../../api/modules/stems.api'
import type { LibrarySong } from '../../api/modules/songs.api'
import type { StemJob } from '../../api/modules/stems.api'
import { addClip, uploadExternalClip } from '../../api/modules/mix.api'
import type { MixClip } from '../../api/modules/mix.api'

interface AddClipModalProps {
  mixId: string
  nextPosition: number
  onAdd: (clip: MixClip) => void
  onClose: () => void
}

type SourceTab = 'library' | 'stems' | 'external'

const MAX_EXTERNAL_FILE_SIZE = 50 * 1024 * 1024
const EXTERNAL_FILE_EXTENSIONS = ['.mp3', '.wav']

function loadAudioFileDurationMs(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const audio = document.createElement('audio')
    const objectUrl = URL.createObjectURL(file)
    audio.preload = 'metadata'

    const cleanup = () => {
      audio.removeAttribute('src')
      audio.load()
      URL.revokeObjectURL(objectUrl)
    }

    audio.onloadedmetadata = () => {
      const durationMs = Math.round(audio.duration * 1000)
      cleanup()
      if (Number.isFinite(durationMs) && durationMs > 0) {
        resolve(durationMs)
      } else {
        reject(new Error('No se pudo determinar la duración del archivo.'))
      }
    }
    audio.onerror = () => {
      cleanup()
      reject(new Error('El archivo no contiene audio legible.'))
    }
    audio.src = objectUrl
  })
}

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDuration(milliseconds: number) {
  const totalSeconds = Math.floor(milliseconds / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function getErrorMessage(error: unknown, fallback: string) {
  if (isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail ?? fallback
  }
  return error instanceof Error ? error.message : fallback
}

function loadStemDurationMs(stemFileId: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const audio = new Audio()
    audio.preload = 'metadata'

    const cleanup = () => {
      audio.removeAttribute('src')
      audio.load()
    }

    audio.onloadedmetadata = () => {
      const durationMs = Math.round(audio.duration * 1000)
      cleanup()
      if (Number.isFinite(durationMs) && durationMs > 0) {
        resolve(durationMs)
      } else {
        reject(new Error('No se pudo determinar la duración del stem.'))
      }
    }
    audio.onerror = () => {
      cleanup()
      reject(new Error('No se pudo leer la duración del stem.'))
    }

    void getStemDownloadUrl(stemFileId)
      .then((url) => {
        audio.src = url
        audio.load()
      })
      .catch((error) => {
        cleanup()
        reject(error)
      })
  })
}

export default function AddClipModal({ mixId, nextPosition, onAdd, onClose }: AddClipModalProps) {
  const [tab, setTab] = useState<SourceTab>('library')
  const [songs, setSongs] = useState<LibrarySong[]>([])
  const [stemJobs, setStemJobs] = useState<StemJob[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [externalFile, setExternalFile] = useState<File | null>(null)
  const [externalDurationMs, setExternalDurationMs] = useState<number | null>(null)
  const [externalProgress, setExternalProgress] = useState<number | null>(null)
  const [readingExternalFile, setReadingExternalFile] = useState(false)
  const [draggingExternalFile, setDraggingExternalFile] = useState(false)
  const externalFileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([getLibrary(), getStemJobs()])
      .then(([s, j]) => {
        setSongs(s)
        setStemJobs(j)
      })
      .finally(() => setLoading(false))
  }, [])

  async function handleAddSong(song: LibrarySong) {
    setAdding(true)
    setError(null)
    try {
      const detail = await getSongDetail(song.id)
      if (!detail.audio_duration || detail.audio_duration <= 0) {
        throw new Error('La canción no tiene una duración válida.')
      }
      const endMs = Math.round(detail.audio_duration * 1000)

      const clip = await addClip(mixId, {
        song_id: song.id,
        position: nextPosition,
        start_time_ms: 0,
        end_time_ms: endMs,
      })
      onAdd(clip)
    } catch (error) {
      setError(getErrorMessage(error, 'Error al agregar el clip.'))
    } finally {
      setAdding(false)
    }
  }

  async function handleAddStem(stemFileId: string, durationMs?: number) {
    setAdding(true)
    setError(null)
    try {
      const resolvedDurationMs =
        durationMs && durationMs > 0 ? Math.round(durationMs) : await loadStemDurationMs(stemFileId)
      const clip = await addClip(mixId, {
        stem_file_id: stemFileId,
        position: nextPosition,
        start_time_ms: 0,
        end_time_ms: resolvedDurationMs,
      })
      onAdd(clip)
    } catch (error) {
      setError(getErrorMessage(error, 'Error al agregar el clip.'))
    } finally {
      setAdding(false)
    }
  }

  function validateExternalFile(file: File) {
    const extension = `.${file.name.split('.').pop()?.toLowerCase()}`
    if (!EXTERNAL_FILE_EXTENSIONS.includes(extension)) {
      return 'Solo se aceptan archivos .mp3 o .wav.'
    }
    if (file.size > MAX_EXTERNAL_FILE_SIZE) {
      return 'El archivo supera el límite de 50 MB.'
    }
    return null
  }

  async function handleExternalFileChange(file?: File) {
    if (!file) {
      return
    }
    setError(null)
    const validationError = validateExternalFile(file)
    if (validationError) {
      setExternalFile(null)
      setExternalDurationMs(null)
      setError(validationError)
      return
    }
    setExternalFile(file)
    setExternalDurationMs(null)
    setReadingExternalFile(true)
    try {
      const durationMs = await loadAudioFileDurationMs(file)
      setExternalDurationMs(durationMs)
    } catch (error) {
      setExternalFile(null)
      setError(getErrorMessage(error, 'No se pudo leer el archivo de audio.'))
    } finally {
      setReadingExternalFile(false)
    }
  }

  function handleExternalDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDraggingExternalFile(false)
    void handleExternalFileChange(event.dataTransfer.files[0])
  }

  function handleExternalInputChange(event: ChangeEvent<HTMLInputElement>) {
    void handleExternalFileChange(event.target.files?.[0])
    event.currentTarget.value = ''
  }

  async function handleAddExternalFile() {
    if (!externalFile || !externalDurationMs || adding || readingExternalFile) {
      return
    }
    setAdding(true)
    setExternalProgress(0)
    setError(null)
    try {
      const clip = await uploadExternalClip(
        mixId,
        {
          file: externalFile,
          position: nextPosition,
          start_time_ms: 0,
          end_time_ms: externalDurationMs,
        },
        setExternalProgress
      )
      onAdd(clip)
    } catch (error) {
      setError(getErrorMessage(error, 'Error al subir el archivo.'))
    } finally {
      setAdding(false)
      setExternalProgress(null)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        background: 'var(--overlay)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={() => !adding && onClose()}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 480,
          maxHeight: '80vh',
          background: 'var(--bg-surface)',
          borderRadius: 12,
          border: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 20px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Agregar clip</h3>
          <button
            onClick={onClose}
            disabled={adding}
            style={{
              background: 'none',
              border: 'none',
              cursor: adding ? 'not-allowed' : 'pointer',
              opacity: adding ? 0.5 : 1,
              color: 'var(--text-subdued)',
              fontSize: 20,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
          {(['library', 'stems', 'external'] as SourceTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              disabled={adding}
              style={{
                flex: 1,
                padding: '10px',
                border: 'none',
                background: 'none',
                borderBottom:
                  tab === t ? '2px solid var(--color-primary)' : '2px solid transparent',
                color: tab === t ? 'var(--text-base)' : 'var(--text-subdued)',
                fontWeight: tab === t ? 700 : 400,
                fontSize: 14,
                cursor: adding ? 'not-allowed' : 'pointer',
                opacity: adding ? 0.6 : 1,
              }}
            >
              {t === 'library'
                ? 'Biblioteca'
                : t === 'stems'
                  ? 'Stems separados'
                  : 'Archivo externo'}
            </button>
          ))}
        </div>

        {error && (
          <div
            style={{
              background: 'var(--color-error-soft)',
              color: 'var(--color-error)',
              fontSize: 13,
              padding: '10px 20px',
            }}
          >
            {error}
          </div>
        )}

        {/* List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {loading && tab !== 'external' ? (
            <div
              style={{
                padding: '20px',
                textAlign: 'center',
                color: 'var(--text-subdued)',
                fontSize: 14,
              }}
            >
              Cargando...
            </div>
          ) : tab === 'external' ? (
            <div style={{ padding: 20 }}>
              <div
                role="button"
                tabIndex={adding || readingExternalFile ? -1 : 0}
                onDragOver={(event) => {
                  event.preventDefault()
                  if (!adding && !readingExternalFile) {
                    setDraggingExternalFile(true)
                  }
                }}
                onDragLeave={() => setDraggingExternalFile(false)}
                onDrop={handleExternalDrop}
                onClick={() => {
                  if (!adding && !readingExternalFile) {
                    externalFileInputRef.current?.click()
                  }
                }}
                onKeyDown={(event) => {
                  if (
                    (event.key === 'Enter' || event.key === ' ') &&
                    !adding &&
                    !readingExternalFile
                  ) {
                    event.preventDefault()
                    externalFileInputRef.current?.click()
                  }
                }}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  minHeight: 150,
                  padding: '24px 20px',
                  border: '2px dashed',
                  borderColor: draggingExternalFile
                    ? 'var(--color-primary)'
                    : 'var(--bg-card-hover)',
                  borderRadius: 10,
                  background: draggingExternalFile ? 'var(--color-primary-soft)' : 'transparent',
                  color: 'var(--text-base)',
                  cursor: adding || readingExternalFile ? 'not-allowed' : 'pointer',
                  opacity: adding || readingExternalFile ? 0.6 : 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                }}
              >
                <img
                  src="/logo.png"
                  alt=""
                  aria-hidden="true"
                  style={{ width: 40, height: 40, objectFit: 'contain' }}
                />
                <strong style={{ display: 'block', fontSize: 13 }}>
                  {readingExternalFile ? 'Leyendo archivo…' : 'Seleccionar archivo de audio'}
                </strong>
                <span style={{ color: 'var(--text-subdued)', fontSize: 12 }}>
                  Arrastra un archivo aquí o selecciona · MP3 o WAV · máximo 50 MB
                </span>
                <input
                  ref={externalFileInputRef}
                  type="file"
                  accept=".mp3,.wav,audio/mpeg,audio/wav"
                  hidden
                  onChange={handleExternalInputChange}
                />
              </div>

              {externalFile && (
                <div
                  style={{
                    marginTop: 14,
                    padding: 12,
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 12,
                      color: 'var(--text-base)',
                      fontSize: 13,
                    }}
                  >
                    <span
                      style={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {externalFile.name}
                    </span>
                    <span style={{ color: 'var(--text-subdued)', flexShrink: 0 }}>
                      {formatFileSize(externalFile.size)}
                    </span>
                  </div>
                  <p style={{ margin: '8px 0 0', color: 'var(--text-subdued)', fontSize: 12 }}>
                    {externalDurationMs
                      ? `Duración: ${formatDuration(externalDurationMs)}`
                      : 'Comprobando duración…'}
                  </p>
                </div>
              )}

              {externalProgress !== null && (
                <div style={{ marginTop: 14 }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      color: 'var(--text-subdued)',
                      fontSize: 12,
                    }}
                  >
                    <span>Subiendo archivo…</span>
                    <span>{externalProgress}%</span>
                  </div>
                  <div
                    style={{
                      height: 5,
                      marginTop: 6,
                      overflow: 'hidden',
                      borderRadius: 999,
                      background: 'var(--border)',
                    }}
                  >
                    <div
                      style={{
                        width: `${externalProgress}%`,
                        height: '100%',
                        background: 'var(--color-primary)',
                        transition: 'width 120ms ease',
                      }}
                    />
                  </div>
                </div>
              )}

              <button
                type="button"
                disabled={!externalFile || !externalDurationMs || adding || readingExternalFile}
                onClick={() => void handleAddExternalFile()}
                style={{
                  width: '100%',
                  marginTop: 16,
                  padding: '10px 12px',
                  border: 'none',
                  borderRadius: 7,
                  background: 'var(--color-primary)',
                  color: 'var(--color-on-primary)',
                  cursor:
                    !externalFile || !externalDurationMs || adding || readingExternalFile
                      ? 'not-allowed'
                      : 'pointer',
                  opacity:
                    !externalFile || !externalDurationMs || adding || readingExternalFile ? 0.5 : 1,
                  fontWeight: 700,
                }}
              >
                {adding ? 'Agregando…' : 'Agregar archivo'}
              </button>
            </div>
          ) : tab === 'library' ? (
            songs.length === 0 ? (
              <div
                style={{
                  padding: '20px',
                  textAlign: 'center',
                  color: 'var(--text-subdued)',
                  fontSize: 14,
                }}
              >
                No tienes canciones en tu biblioteca.
              </div>
            ) : (
              songs.map((song) => (
                <button
                  key={song.id}
                  onClick={() => !adding && handleAddSong(song)}
                  disabled={adding}
                  style={{
                    width: '100%',
                    padding: '10px 20px',
                    background: 'none',
                    border: 'none',
                    cursor: adding ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    textAlign: 'left',
                    transition: 'background 0.1s',
                    opacity: adding ? 0.5 : 1,
                  }}
                  onMouseEnter={(e) => {
                    if (!adding) {
                      ;(e.currentTarget as HTMLButtonElement).style.background =
                        'var(--bg-card-hover)'
                    }
                  }}
                  onMouseLeave={(e) =>
                    ((e.currentTarget as HTMLButtonElement).style.background = 'none')
                  }
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 4,
                      background: 'var(--bg-card-hover)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--color-primary)',
                      flexShrink: 0,
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
                    </svg>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p
                      style={{
                        margin: 0,
                        fontSize: 14,
                        fontWeight: 500,
                        color: 'var(--text-base)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {song.title}
                    </p>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text-subdued)' }}>
                      {song.tags
                        ?.slice(0, 3)
                        .map((t) => t.name)
                        .join(', ') || 'Sin tags'}
                    </p>
                  </div>
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    style={{ color: 'var(--text-subdued)', flexShrink: 0 }}
                  >
                    <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
                  </svg>
                </button>
              ))
            )
          ) : stemJobs.filter(
              (j) => j.status === 'completed' && j.stem_files && j.stem_files.length > 0
            ).length === 0 ? (
            <div
              style={{
                padding: '20px',
                textAlign: 'center',
                color: 'var(--text-subdued)',
                fontSize: 14,
              }}
            >
              No tienes stems separados disponibles.
            </div>
          ) : (
            stemJobs
              .filter((j) => j.status === 'completed' && j.stem_files && j.stem_files.length > 0)
              .flatMap((j) => j.stem_files!.map((sf) => ({ job: j, sf })))
              .map(({ job, sf }) => (
                <button
                  key={sf.id}
                  onClick={() =>
                    !adding &&
                    handleAddStem(
                      sf.id,
                      sf.duration_seconds ? Math.round(sf.duration_seconds * 1000) : undefined
                    )
                  }
                  disabled={adding}
                  style={{
                    width: '100%',
                    padding: '10px 20px',
                    background: 'none',
                    border: 'none',
                    cursor: adding ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    textAlign: 'left',
                    transition: 'background 0.1s',
                    opacity: adding ? 0.5 : 1,
                  }}
                  onMouseEnter={(e) => {
                    if (!adding) {
                      ;(e.currentTarget as HTMLButtonElement).style.background =
                        'var(--bg-card-hover)'
                    }
                  }}
                  onMouseLeave={(e) =>
                    ((e.currentTarget as HTMLButtonElement).style.background = 'none')
                  }
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 4,
                      background: 'var(--color-success-soft)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--color-success)',
                      flexShrink: 0,
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: 'uppercase',
                    }}
                  >
                    {sf.stem_type.replace('no_vocals', 'kara').slice(0, 4)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p
                      style={{
                        margin: 0,
                        fontSize: 14,
                        fontWeight: 500,
                        color: 'var(--text-base)',
                      }}
                    >
                      {sf.stem_type.replace('no_vocals', 'Karaoke').replace('_', ' ')}
                    </p>
                    <p
                      style={{
                        margin: 0,
                        fontSize: 12,
                        color: 'var(--text-subdued)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {job.source_filename}
                    </p>
                  </div>
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    style={{ color: 'var(--text-subdued)', flexShrink: 0 }}
                  >
                    <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
                  </svg>
                </button>
              ))
          )}
        </div>
      </div>
    </div>
  )
}
