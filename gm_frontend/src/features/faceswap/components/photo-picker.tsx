import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { ImageUp } from 'lucide-react'

import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { FACESWAP_MAX_PHOTO_MB } from '../types/faceswap.types'
import { formatFileSize } from './faceswap-ui'
import { PHOTO_ACCEPT, validatePhoto } from './faceswap-validation'

interface Props {
  file: File | null
  onChange: (file: File | null) => void
  disabled?: boolean
}

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
        <div className="flex items-center gap-4 rounded-xl bg-card-hover p-3">
          <img
            src={preview}
            alt="Tu foto"
            className="h-14 w-14 shrink-0 rounded-full border-2 border-primary object-cover"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{file.name}</p>
            <p className="text-xs text-muted">{formatFileSize(file.size)}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            Cambiar foto
          </Button>
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
          className={cn(
            'flex flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors disabled:opacity-60',
            dragging
              ? 'border-primary bg-primary-soft'
              : 'border-border-strong hover:border-primary'
          )}
        >
          <ImageUp size={26} className="text-primary" aria-hidden="true" />
          <span className="text-sm font-medium text-white">
            Arrastra tu foto o <span className="text-primary">selecciónala</span>
          </span>
          <span className="text-xs text-muted">
            JPG, PNG o WEBP · máx. {FACESWAP_MAX_PHOTO_MB} MB · de frente y con buena luz
          </span>
        </button>
      )}
      <input ref={inputRef} type="file" accept={PHOTO_ACCEPT} className="hidden" onChange={onInput} />
      {error && (
        <p className="px-1 text-xs text-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
