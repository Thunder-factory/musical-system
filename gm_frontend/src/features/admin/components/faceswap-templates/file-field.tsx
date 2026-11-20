import { useId, useRef, useState } from 'react'
import { Upload, X } from 'lucide-react'

interface FileFieldProps {
  label: string
  accept: string
  help?: string
  buttonText?: string
  onChange: (file: File | null) => void
}

function formatBytes(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileField({
  label,
  accept,
  help,
  buttonText = 'Seleccionar archivo',
  onChange,
}: FileFieldProps) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [selected, setSelected] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)

  function pick(file: File | null) {
    setSelected(file)
    onChange(file)
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-xs font-semibold text-muted">
        {label}
      </label>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          const f = e.dataTransfer.files[0] ?? null
          if (f) {
            pick(f)
          }
        }}
        className={`flex items-center justify-between gap-3 rounded-lg border border-dashed px-3 py-2.5 transition-colors ${
          dragging ? 'border-primary bg-primary-soft' : 'border-border-strong bg-card-hover'
        }`}
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-surface px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-border-strong"
          >
            <Upload size={13} aria-hidden="true" />
            {selected ? 'Cambiar' : buttonText}
          </button>

          <span className="truncate text-xs text-muted">
            {selected ? `${selected.name} (${formatBytes(selected.size)})` : 'Ningún archivo seleccionado'}
          </span>
        </div>

        {selected && (
          <button
            type="button"
            onClick={() => {
              if (inputRef.current) {
                inputRef.current.value = ''
              }
              pick(null)
            }}
            aria-label="Quitar archivo seleccionado"
            className="rounded p-1 text-muted hover:bg-surface hover:text-white"
          >
            <X size={14} aria-hidden="true" />
          </button>
        )}

        <input
          id={inputId}
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
      </div>

      {help && <span className="text-xs text-muted">{help}</span>}
    </div>
  )
}
