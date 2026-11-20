import { useState } from 'react'
import type { FormEvent } from 'react'
import { LoaderCircle } from 'lucide-react'

import type { AdminFaceSwapTemplate, TemplateFormValues } from '../../../types/faceswap.types'
import { BTN_GHOST, BTN_PRIMARY, INPUT } from '../faceswap-ui'
import { PHOTO_ACCEPT, VIDEO_ACCEPT, validateTemplateForm } from '../faceswap-validation'
import FileField from './file-field'

interface Props {
  initial: AdminFaceSwapTemplate | null
  submitting: boolean
  error: string | null
  onSubmit: (values: TemplateFormValues) => void
  onCancel: () => void
}

const LABEL = 'flex flex-col gap-1.5 text-xs font-bold text-white'

/** Formulario de crear/editar plantilla. El video solo se elige al crear. */
export default function TemplateForm({ initial, submitting, error, onSubmit, onCancel }: Props) {
  const [title, setTitle] = useState(initial?.title ?? '')
  const [refTime, setRefTime] = useState(initial?.ref_time_s?.toString() ?? '')
  const [isActive, setIsActive] = useState(initial?.is_active ?? true)
  const [video, setVideo] = useState<File | null>(null)
  const [thumbnail, setThumbnail] = useState<File | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const editing = Boolean(initial)

  function submit(e: FormEvent) {
    e.preventDefault()
    const refTimeS = refTime.trim() === '' ? null : Number(refTime)
    const needsVideo = !editing && !video
    const maxSeconds = initial?.duration_seconds
    const invalid = validateTemplateForm({ title, refTimeS, needsVideo, maxSeconds })
    setLocalError(invalid)
    if (!invalid) {
      onSubmit({
        title,
        refTimeS,
        isActive,
        video: video ?? undefined,
        thumbnail: thumbnail ?? undefined,
      })
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-lg bg-card p-5">
      <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
        {editing ? `Editar: ${initial?.title}` : 'Nueva plantilla'}
      </h2>
      <label className={LABEL}>
        Título
        <input
          className={INPUT}
          value={title}
          maxLength={120}
          placeholder="Ej. Oficina — diario"
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>
      {!editing && (
        <FileField
          label="Video (MP4, MOV o WEBM · máx. 15 s y 50 MB)"
          accept={VIDEO_ACCEPT}
          onChange={setVideo}
        />
      )}
      <FileField
        label="Miniatura (opcional · JPG, PNG o WEBP ≤ 2 MB)"
        accept={PHOTO_ACCEPT}
        help="Si la dejas vacía se genera desde el video."
        onChange={setThumbnail}
      />
      <label className={LABEL}>
        Segundo de referencia
        <input
          type="number"
          step={0.1}
          min={0}
          className={INPUT}
          value={refTime}
          placeholder="Vacío = cara más grande"
          onChange={(e) => setRefTime(e.target.value)}
        />
        <span className="font-normal text-muted">
          Un segundo donde solo se vea la cara a reemplazar. Vacío: se usa la cara más grande.
        </span>
      </label>
      <label className="flex cursor-pointer items-center gap-2 text-sm text-white">
        <input
          type="checkbox"
          checked={isActive}
          onChange={(e) => setIsActive(e.target.checked)}
          className="h-4 w-4"
          style={{ accentColor: 'var(--color-primary)' }}
        />
        Visible para los usuarios
      </label>
      {(localError ?? error) && (
        <p className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {localError ?? error}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" className={BTN_PRIMARY} disabled={submitting}>
          {submitting && <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />}
          {submitting ? 'Guardando…' : 'Guardar plantilla'}
        </button>
        {editing && (
          <button type="button" className={BTN_GHOST} onClick={onCancel} disabled={submitting}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  )
}
