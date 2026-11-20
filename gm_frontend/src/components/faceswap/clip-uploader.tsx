import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { Info, Video } from 'lucide-react'

import {
  FACESWAP_MAX_SECONDS,
  FACESWAP_MAX_VIDEO_MB,
  formatClipDuration,
} from '../../types/faceswap.types'
import { BTN_GHOST, formatFileSize } from './faceswap-ui'
import { VIDEO_ACCEPT, validateClip } from './faceswap-validation'

interface Props {
  file: File | null
  /** Object URL del clip (la crea el formulario y la comparte con el selector de personaje). */
  previewUrl: string | null
  onChange: (file: File | null) => void
  disabled?: boolean
}

/** Paso 2 (Mi clip): selector de video propio de hasta 15 s con preview. */
export default function ClipUploader({ file, previewUrl, onChange, disabled = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [duration, setDuration] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reading, setReading] = useState(false)

  async function onInput(e: ChangeEvent<HTMLInputElement>) {
    const next = e.target.files?.[0]
    e.target.value = ''
    if (!next) {
      return
    }
    setReading(true)
    const result = await validateClip(next)
    setReading(false)
    setError(result.error)
    setDuration(result.duration)
    if (result.error) {
      return onChange(null)
    }
    onChange(next)
  }

  return (
    <div className="flex flex-col gap-3">
      {file && previewUrl ? (
        <div className="flex items-center gap-3 rounded-lg bg-card-hover p-3">
          <video
            src={previewUrl}
            muted
            playsInline
            className="h-20 w-14 shrink-0 rounded-md bg-surface object-cover"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{file.name}</p>
            <p className="text-xs text-muted">
              {duration != null ? formatClipDuration(duration) : '—'} · {formatFileSize(file.size)}
            </p>
          </div>
          <button
            type="button"
            className={BTN_GHOST}
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            Cambiar clip
          </button>
        </div>
      ) : (
        <button
          type="button"
          disabled={disabled || reading}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-7 text-center transition-colors hover:border-primary disabled:opacity-60"
          style={{ borderColor: 'var(--border-strong)' }}
        >
          <Video size={28} className="text-primary" aria-hidden="true" />
          <span className="text-sm font-medium text-white">
            {reading ? 'Leyendo video…' : 'Selecciona un clip de tu equipo'}
          </span>
          <span className="text-xs text-muted">
            MP4, MOV o WEBM · máx. {FACESWAP_MAX_SECONDS} s y {FACESWAP_MAX_VIDEO_MB} MB
          </span>
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={VIDEO_ACCEPT}
        className="hidden"
        onChange={onInput}
      />
      {error && (
        <p className="px-1 text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
      <p className="flex items-center gap-1.5 text-xs text-muted">
        <Info size={13} aria-hidden="true" />
        Debajo puedes elegir a qué persona cambiarle la cara.
      </p>
    </div>
  )
}
