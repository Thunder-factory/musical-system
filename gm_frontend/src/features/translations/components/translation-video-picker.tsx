import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { FileVideo } from 'lucide-react'

import { cn } from '../../../lib/cn'
import type { TranslationConfig } from '../api/translations.api'
import { formatDuration, formatFileSize, readVideoDuration } from '../lib/translation-constants'

interface TranslationVideoPickerProps {
  config: TranslationConfig
  file: File | null
  disabled: boolean
  onChange: (file: File | null, error: string | null) => void
}

export default function TranslationVideoPicker({
  config,
  file,
  disabled,
  onChange,
}: TranslationVideoPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    if (!file && inputRef.current) {
      inputRef.current.value = ''
    }
  }, [file])

  async function validateAndSelect(candidate: File) {
    const extension = `.${candidate.name.split('.').pop()?.toLowerCase() ?? ''}`
    if (!config.allowed_extensions.includes(extension)) {
      onChange(null, 'Solo se aceptan videos MP4, MOV o WebM.')
      return
    }
    if (candidate.size > config.max_file_size_mb * 1024 * 1024) {
      onChange(
        null,
        `El video supera el límite de ${config.max_file_size_mb} MB (${formatFileSize(candidate.size)}).`
      )
      return
    }
    const duration = await readVideoDuration(candidate)
    if (duration != null && duration > config.max_duration_seconds) {
      onChange(
        null,
        `El video dura ${formatDuration(duration)}; el máximo es ${formatDuration(config.max_duration_seconds)}.`
      )
      return
    }
    onChange(candidate, null)
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault()
    setDragging(false)
    if (disabled) {
      return
    }
    const dropped = event.dataTransfer.files[0]
    if (dropped) {
      void validateAndSelect(dropped)
    }
  }

  function onInput(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0]
    if (selected) {
      void validateAndSelect(selected)
    }
  }

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) {
            setDragging(true)
          }
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition-colors disabled:cursor-not-allowed disabled:opacity-60',
          dragging
            ? 'border-primary bg-primary-soft'
            : 'border-border-strong hover:border-primary'
        )}
      >
        <FileVideo size={32} className="text-primary" aria-hidden="true" />
        {file ? (
          <>
            <span className="break-all text-sm font-semibold text-white">{file.name}</span>
            <span className="text-xs text-muted">
              {file.name.split('.').pop()?.toUpperCase()} · {formatFileSize(file.size)} · haz clic
              para cambiarlo
            </span>
          </>
        ) : (
          <>
            <span className="text-sm font-medium text-white">
              Arrastra un video musical aquí o <span className="text-primary">selecciona</span>
            </span>
            <span className="text-xs text-muted">
              MP4, MOV o WebM — hasta {config.max_file_size_mb} MB y{' '}
              {config.max_duration_seconds / 60} minutos
            </span>
          </>
        )}
      </button>

      <input
        ref={inputRef}
        type="file"
        accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
        className="sr-only"
        onChange={onInput}
        disabled={disabled}
      />
    </>
  )
}
