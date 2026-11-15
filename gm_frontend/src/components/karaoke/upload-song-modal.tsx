import { useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { X } from 'lucide-react'
import axios from 'axios'
import { uploadSong } from '../../api/modules/songs.api'
import type { UploadSongResponse } from '../../api/modules/songs.api'

const MAX_SIZE = 50 * 1024 * 1024
const ALLOWED_EXTENSIONS = ['.mp3', '.wav']

interface Props {
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

export default function UploadSongModal({ onClose, onUploaded }: Props) {
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
    if (nextFile) chooseFile(nextFile)
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    const nextFile = event.dataTransfer.files[0]
    if (nextFile) chooseFile(nextFile)
  }

  async function handleSubmit() {
    if (!file || uploading) return
    setUploading(true)
    setError(null)
    try {
      const song = await uploadSong(file, title, setProgress)
      onUploaded(song)
    } catch (error: unknown) {
      const detail = axios.isAxiosError(error)
        ? (error.response?.data?.detail ?? error.response?.data?.error)
        : null
      setError(
        typeof detail === 'string'
          ? detail
          : 'No se pudo subir la canción. Verifica el archivo e inténtalo nuevamente.',
      )
      setProgress(0)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div style={overlayStyle} role="presentation" onClick={() => !uploading && onClose()}>
      <div style={dialogStyle} role="dialog" aria-modal="true" aria-labelledby="upload-song-title" onClick={(event) => event.stopPropagation()}>
        <div style={headerStyle}>
          <h2 id="upload-song-title" style={{ margin: 0, fontSize: 20 }}>Subir música</h2>
          <button type="button" onClick={onClose} disabled={uploading} style={closeStyle} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>
        <p style={{ margin: '0 0 16px', color: 'var(--text-subdued)', fontSize: 13 }}>
          La canción quedará privada en tu biblioteca y no se generará Karaoke automáticamente.
        </p>
        <div
          onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          style={{ ...dropzoneStyle, borderColor: dragging ? 'var(--color-primary)' : 'var(--border)' }}
        >
          <strong>{file ? file.name : 'Arrastra un MP3/WAV aquí'}</strong>
          <span style={{ color: 'var(--text-subdued)', fontSize: 12 }}>o selecciona un archivo · máximo 50 MB</span>
          <input
            ref={inputRef}
            type="file"
            accept=".mp3,.wav,audio/mpeg,audio/wav"
            hidden
            onClick={(event) => event.stopPropagation()}
            onChange={handleInput}
          />
        </div>
        <label style={labelStyle}>
          Título
          <input value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} style={inputStyle} placeholder="Título de la canción" />
        </label>
        {uploading && <progress value={progress} max={100} style={{ width: '100%' }} />}
        {error && <p role="alert" style={{ color: 'var(--color-error)', fontSize: 13 }}>{error}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
          <button type="button" onClick={onClose} disabled={uploading} style={secondaryButtonStyle}>Cancelar</button>
          <button type="button" onClick={() => void handleSubmit()} disabled={!file || !title.trim() || uploading} style={primaryButtonStyle}>
            {uploading ? `Subiendo ${progress}%…` : 'Subir música'}
          </button>
        </div>
      </div>
    </div>
  )
}

const overlayStyle = { position: 'fixed' as const, inset: 0, zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, background: 'var(--overlay)' }
const dialogStyle = { width: 'min(100%, 480px)', padding: 24, borderRadius: 14, background: 'var(--bg-surface)', border: '1px solid var(--border)', boxShadow: 'var(--shadow)' }
const headerStyle = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }
const closeStyle = { display: 'grid', placeItems: 'center', padding: 6, border: 0, background: 'transparent', color: 'var(--text-subdued)', cursor: 'pointer' }
const dropzoneStyle = { display: 'flex', flexDirection: 'column' as const, alignItems: 'center', gap: 8, padding: 28, border: '2px dashed', borderRadius: 12, cursor: 'pointer', textAlign: 'center' as const }
const labelStyle = { display: 'flex', flexDirection: 'column' as const, gap: 6, marginTop: 16, fontSize: 13, fontWeight: 600 }
const inputStyle = { padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-card-hover)', color: 'var(--text-base)', fontSize: 14 }
const secondaryButtonStyle = { padding: '10px 14px', border: '1px solid var(--border)', borderRadius: 8, background: 'transparent', color: 'var(--text-base)', cursor: 'pointer' }
const primaryButtonStyle = { padding: '10px 14px', border: 0, borderRadius: 8, background: 'var(--color-primary)', color: 'var(--bg-base)', fontWeight: 700, cursor: 'pointer' }
