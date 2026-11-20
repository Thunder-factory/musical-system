import { useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from 'react'
import axios from 'axios'
import { Upload } from 'lucide-react'

import { Button, FormField, Input, Modal } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { uploadSong, type UploadSongResponse } from '../../songs/api/songs.api'

const MAX_SIZE = 50 * 1024 * 1024
const ALLOWED_EXTENSIONS = ['.mp3', '.wav']

interface UploadSongModalProps {
  open: boolean
  onClose: () => void
  onUploaded: (song: UploadSongResponse) => void
}

function validateFile(file: File): string | null {
  const extension = `.${file.name.split('.').pop()?.toLowerCase()}`
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return 'Solo se aceptan archivos MP3 o WAV.'
  }
  if (file.size <= 0) {
    return 'El archivo está vacío.'
  }
  if (file.size > MAX_SIZE) {
    return 'El archivo supera el límite de 50 MB.'
  }
  return null
}

export default function UploadSongModal({ open, onClose, onUploaded }: UploadSongModalProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  function chooseFile(nextFile: File) {
    const validationError = validateFile(nextFile)
    setError(validationError)
    if (!validationError) {
      setFile(nextFile)
      if (!title.trim()) {
        setTitle(nextFile.name.replace(/\.[^.]+$/, ''))
      }
    } else {
      setFile(null)
    }
  }

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0]
    if (nextFile) {
      chooseFile(nextFile)
    }
    event.currentTarget.value = ''
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    const nextFile = event.dataTransfer.files[0]
    if (nextFile && !uploading) {
      chooseFile(nextFile)
    }
  }

  function handleDropzoneKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if ((event.key === 'Enter' || event.key === ' ') && !uploading) {
      event.preventDefault()
      inputRef.current?.click()
    }
  }

  async function handleSubmit() {
    if (!file || uploading) {
      return
    }
    setUploading(true)
    setError(null)
    try {
      const song = await uploadSong(file, title, setProgress)
      toast.success('Canción subida', `"${song.title}" ya está disponible en tu biblioteca.`)
      setFile(null)
      setTitle('')
      setProgress(0)
      onUploaded(song)
    } catch (err: unknown) {
      const detail = axios.isAxiosError(err)
        ? (err.response?.data?.detail ?? err.response?.data?.error)
        : null
      setError(
        typeof detail === 'string'
          ? detail
          : 'No se pudo subir la canción. Verifica el archivo e inténtalo de nuevo.'
      )
      setProgress(0)
    } finally {
      setUploading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Subir música" size="md" preventClose={uploading}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          La canción quedará privada en tu biblioteca y podrás usarla para generar un karaoke.
        </p>

        <div
          role="button"
          tabIndex={uploading ? -1 : 0}
          onDragOver={(e) => {
            e.preventDefault()
            if (!uploading) {
              setDragging(true)
            }
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !uploading && inputRef.current?.click()}
          onKeyDown={handleDropzoneKeyDown}
          aria-label="Seleccionar archivo MP3 o WAV"
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-7 text-center transition-colors ${
            dragging
              ? 'border-primary bg-primary-soft'
              : 'border-border-strong bg-surface hover:border-primary/60'
          } ${uploading ? 'cursor-not-allowed opacity-60' : ''}`}
        >
          <Upload size={22} className="text-primary" aria-hidden="true" />
          <strong className="text-sm font-semibold text-white">
            {file ? file.name : 'Arrastra un MP3 o WAV aquí'}
          </strong>
          <span className="text-xs text-muted">o haz clic para elegir · máximo 50 MB</span>
          <input
            ref={inputRef}
            type="file"
            accept=".mp3,.wav,audio/mpeg,audio/wav"
            className="sr-only"
            onChange={handleInput}
          />
        </div>

        <FormField label="Título" required>
          <Input
            value={title}
            maxLength={200}
            disabled={uploading}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Título de la canción"
          />
        </FormField>

        {uploading && (
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-muted">
              <span>Subiendo audio...</span>
              <span className="tabular-nums">{progress}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-card-hover">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {error && (
          <p role="alert" className="text-xs text-error">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose} disabled={uploading}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleSubmit()}
            loading={uploading}
            disabled={!file || !title.trim() || uploading}
          >
            {uploading ? `Subiendo ${progress}%...` : 'Subir música'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
