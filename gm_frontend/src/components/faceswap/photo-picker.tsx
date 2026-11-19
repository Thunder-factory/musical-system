import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { ImageUp } from 'lucide-react'

import { FACESWAP_MAX_PHOTO_MB } from '../../types/faceswap.types'
import { BTN_GHOST, formatFileSize } from './faceswap-ui'
import { PHOTO_ACCEPT, validatePhoto } from './faceswap-validation'

interface Props {
  file: File | null
  onChange: (file: File | null) => void
  disabled?: boolean
}

/** Paso 1: selección de la foto de la cara con preview circular. */
export default function PhotoPicker({ file, onChange, disabled = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    if (!file) {
      setPreview(null)
      return
    }
    const url = URL.createObjectURL(file)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  function handle(next: File | undefined) {
    if (!next || disabled) {
      return
    }
    const err = validatePhoto(next)
    setError(err)
    onChange(err ? null : next)
  }

  function onDrop(e: DragEvent<HTMLButtonElement>) {
    e.preventDefault()
    setDragging(false)
    handle(e.dataTransfer.files[0])
  }

  function onInput(e: ChangeEvent<HTMLInputElement>) {
    handle(e.target.files?.[0])
    e.target.value = ''
  }

  return (
    <div className="flex flex-col gap-2">
      {preview && file ? (
        <div className="flex items-center gap-4 rounded-lg bg-card-hover p-3">
          <img
            src={preview}
            alt="Tu foto"
            className="h-16 w-16 shrink-0 rounded-full object-cover"
            style={{ border: '2px solid var(--color-primary)' }}
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{file.name}</p>
            <p className="text-xs text-muted">{formatFileSize(file.size)}</p>
          </div>
          <button
            type="button"
            className={BTN_GHOST}
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            Cambiar foto
          </button>
        </div>
      ) : (
        <button
          type="button"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className="flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-7 text-center transition-colors disabled:opacity-60"
          style={{
            borderColor: dragging ? 'var(--color-primary)' : 'var(--border-strong)',
            background: dragging ? 'var(--color-primary-soft)' : 'transparent',
          }}
        >
          <ImageUp size={28} className="text-primary" aria-hidden="true" />
          <span className="text-sm font-medium text-white">
            Arrastra tu foto o <span className="text-primary">selecciónala</span>
          </span>
          <span className="text-xs text-muted">
            JPG, PNG o WEBP · máx. {FACESWAP_MAX_PHOTO_MB} MB · de frente y con buena luz
          </span>
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={PHOTO_ACCEPT}
        className="hidden"
        onChange={onInput}
      />
      {error && (
        <p className="px-1 text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
    </div>
  )
}
