import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { Music2, Upload, X } from 'lucide-react'

import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { STEM_CREDIT_COST } from '../api/stems.api'

const MAX_SIZE = 50 * 1024 * 1024
const ALLOWED_EXTS = ['.mp3', '.wav']

interface AudioUploaderProps {
  onSubmit: (file: File) => void
  onFileSelected?: () => void
  resetKey?: number
  loading: boolean
  insufficientCredits: boolean
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function AudioUploader({
  onSubmit,
  onFileSelected,
  resetKey = 0,
  loading,
  insufficientCredits,
}: AudioUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    setFile(null)
    setValidationError(null)
    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }, [resetKey])

  function validate(candidate: File): string | null {
    const ext = `.${candidate.name.split('.').pop()?.toLowerCase() ?? ''}`
    if (!ALLOWED_EXTS.includes(ext)) {
      return 'Solo se aceptan archivos .mp3 o .wav'
    }
    if (candidate.size > MAX_SIZE) {
      return `El archivo supera el límite de 50 MB (${(candidate.size / 1024 / 1024).toFixed(1)} MB)`
    }
    return null
  }

  function handleFile(candidate: File) {
    onFileSelected?.()
    const err = validate(candidate)
    setValidationError(err)
    setFile(err ? null : candidate)
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault()
    setDragging(false)
    const dropped = event.dataTransfer.files[0]
    if (dropped) {
      handleFile(dropped)
    }
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0]
    if (selected) {
      handleFile(selected)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <button
        type="button"
        disabled={loading}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'flex w-full flex-col items-center gap-2.5 rounded-xl border-2 border-dashed p-7 text-center transition-colors disabled:cursor-not-allowed disabled:opacity-60',
          dragging
            ? 'border-primary bg-primary-soft'
            : 'border-border-strong bg-transparent hover:border-primary'
        )}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-soft text-primary">
          <Upload size={22} aria-hidden="true" />
        </span>
        <span className="text-sm font-medium text-white">
          Arrastra un archivo aquí o <span className="text-primary">selecciona desde tu equipo</span>
        </span>
        <span className="text-xs text-muted">Formatos .mp3 o .wav — máximo 50 MB</span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept=".mp3,.wav,audio/mpeg,audio/wav"
        className="sr-only"
        onChange={onInputChange}
        disabled={loading}
      />

      {validationError && (
        <p className="text-sm text-error" role="alert">
          {validationError}
        </p>
      )}

      {file && !validationError && (
        <div className="flex items-center justify-between gap-3 rounded-xl bg-card-hover px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <Music2 size={18} className="shrink-0 text-primary" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-white">{file.name}</p>
              <p className="text-xs text-muted">
                {file.name.split('.').pop()?.toUpperCase()} · {formatSize(file.size)}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setFile(null)
              if (inputRef.current) {
                inputRef.current.value = ''
              }
            }}
            aria-label="Quitar archivo seleccionado"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted hover:bg-card hover:text-white"
          >
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          loading={loading}
          disabled={!file || Boolean(validationError) || insufficientCredits || loading}
          costCredits={STEM_CREDIT_COST}
          onClick={() => file && onSubmit(file)}
        >
          {loading ? 'Separando…' : 'Separar pistas'}
        </Button>
      </div>
    </div>
  )
}
