import { useState, type FormEvent } from 'react'

import { Button, FormField, Input } from '../../../../components/ui'
import type { AdminFaceSwapTemplate, TemplateFormValues } from '../../../faceswap/types/faceswap.types'
import FileField from './file-field'
import { PHOTO_ACCEPT, VIDEO_ACCEPT, validateTemplateForm } from './template-validation'

interface Props {
  initial: AdminFaceSwapTemplate | null
  submitting: boolean
  error: string | null
  onSubmit: (values: TemplateFormValues) => void
  onCancel: () => void
}

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
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5">
      <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
        {editing ? `Editar: ${initial?.title}` : 'Nueva plantilla'}
      </h2>

      <FormField label="Título" required>
        <Input
          value={title}
          maxLength={120}
          placeholder="Ej. Escenario — concierto"
          onChange={(e) => setTitle(e.target.value)}
          disabled={submitting}
        />
      </FormField>

      {!editing && (
        <FileField
          label="Video (MP4, MOV o WEBM · máx. 15 s y 50 MB)"
          accept={VIDEO_ACCEPT}
          buttonText="Elegir video"
          onChange={setVideo}
        />
      )}

      <FileField
        label="Miniatura (opcional · JPG, PNG o WEBP ≤ 2 MB)"
        accept={PHOTO_ACCEPT}
        buttonText="Elegir miniatura"
        help="Si la dejas vacía se genera automáticamente desde el video."
        onChange={setThumbnail}
      />

      <FormField
        label="Segundo de referencia"
        hint="Un segundo donde solo se vea la cara a reemplazar. Vacío: se usa la cara más grande."
      >
        <Input
          type="number"
          step={0.1}
          min={0}
          value={refTime}
          placeholder="Vacío = cara más grande"
          onChange={(e) => setRefTime(e.target.value)}
          disabled={submitting}
        />
      </FormField>

      <label className="flex cursor-pointer items-center gap-2 text-sm text-white">
        <input
          type="checkbox"
          checked={isActive}
          onChange={(e) => setIsActive(e.target.checked)}
          className="h-4 w-4 accent-primary"
          disabled={submitting}
        />
        <span>Visible para los usuarios</span>
      </label>

      {(localError ?? error) && (
        <p role="alert" className="text-xs text-error">
          {localError ?? error}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" loading={submitting}>
          {submitting ? 'Guardando...' : 'Guardar plantilla'}
        </Button>
        {editing && (
          <Button variant="ghost" onClick={onCancel} disabled={submitting}>
            Cancelar
          </Button>
        )}
      </div>
    </form>
  )
}
