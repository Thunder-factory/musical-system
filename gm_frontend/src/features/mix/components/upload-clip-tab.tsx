import { useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from 'react'
import { Upload } from 'lucide-react'

import { Button } from '../../../components/ui'

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
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDuration(ms: number) {
  const sec = Math.floor(ms / 1000)
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
}

interface UploadClipTabProps {
  adding: boolean
  progress: number | null
  onError: (message: string | null) => void
  onUpload: (file: File, durationMs: number) => Promise<void>
}

export default function UploadClipTab({
  adding,
  progress,
  onError,
  onUpload,
}: UploadClipTabProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [durationMs, setDurationMs] = useState<number | null>(null)
  const [reading, setReading] = useState(false)
  const [dragging, setDragging] = useState(false)

  async function chooseFile(next?: File) {
    if (!next) {
      return
    }
    onError(null)
    const ext = `.${next.name.split('.').pop()?.toLowerCase()}`
    if (!EXTERNAL_FILE_EXTENSIONS.includes(ext)) {
      setFile(null)
      setDurationMs(null)
      onError('Solo se aceptan archivos .mp3 o .wav.')
      return
    }
    if (next.size > MAX_EXTERNAL_FILE_SIZE) {
      setFile(null)
      setDurationMs(null)
      onError('El archivo supera el límite de 50 MB.')
      return
    }
    setFile(next)
    setDurationMs(null)
    setReading(true)
    try {
      setDurationMs(await loadAudioFileDurationMs(next))
    } catch (err) {
      setFile(null)
      onError(err instanceof Error ? err.message : 'No se pudo leer el archivo de audio.')
    } finally {
      setReading(false)
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    if (!adding && !reading) {
      void chooseFile(event.dataTransfer.files[0])
    }
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    void chooseFile(event.target.files?.[0])
    event.currentTarget.value = ''
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if ((event.key === 'Enter' || event.key === ' ') && !adding && !reading) {
      event.preventDefault()
      inputRef.current?.click()
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div
        role="button"
        tabIndex={adding || reading ? -1 : 0}
        onDragOver={(e) => {
          e.preventDefault()
          if (!adding && !reading) {
            setDragging(true)
          }
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !adding && !reading && inputRef.current?.click()}
        onKeyDown={handleKeyDown}
        aria-label="Seleccionar archivo MP3 o WAV"
        className={`flex min-h-[140px] cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-5 text-center transition-colors ${
          dragging ? 'border-primary bg-primary-soft' : 'border-border-strong hover:border-primary/60'
        } ${adding || reading ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        <Upload size={22} className="text-primary" aria-hidden="true" />
        <strong className="text-sm font-semibold text-white">
          {reading ? 'Leyendo archivo...' : 'Seleccionar archivo de audio'}
        </strong>
        <span className="text-xs text-muted">
          Arrastra un archivo aquí o selecciona · MP3 o WAV · máximo 50 MB
        </span>
        <input
          ref={inputRef}
          type="file"
          accept=".mp3,.wav,audio/mpeg,audio/wav"
          className="sr-only"
          onChange={handleInputChange}
        />
      </div>

      {file && (
        <div className="rounded-lg border border-border bg-surface p-3 text-xs">
          <div className="flex items-center justify-between gap-3 text-white">
            <span className="truncate font-medium">{file.name}</span>
            <span className="shrink-0 text-muted">{formatFileSize(file.size)}</span>
          </div>
          <p className="mt-1 text-muted">
            {durationMs ? `Duración: ${formatDuration(durationMs)}` : 'Comprobando duración...'}
          </p>
        </div>
      )}

      {progress !== null && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-muted">
            <span>Subiendo archivo...</span>
            <span className="tabular-nums">{progress}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-card-hover">
            <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      <Button
        variant="primary"
        loading={adding}
        disabled={!file || !durationMs || adding || reading}
        onClick={() => file && durationMs && void onUpload(file, durationMs)}
        className="w-full"
      >
        {adding ? 'Agregando...' : 'Agregar archivo'}
      </Button>
    </div>
  )
}
