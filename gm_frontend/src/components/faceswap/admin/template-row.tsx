import { Eye, EyeOff, Pencil, Trash2 } from 'lucide-react'

import { formatClipDuration } from '../../../types/faceswap.types'
import type { AdminFaceSwapTemplate } from '../../../types/faceswap.types'
import { BTN_GHOST, softTone } from '../faceswap-ui'

interface Props {
  template: AdminFaceSwapTemplate
  busy: boolean
  onEdit: () => void
  onToggle: () => void
  onDelete: () => void
}

/** Fila de la tabla admin de plantillas con acciones ghost. */
export default function TemplateRow({ template, busy, onEdit, onToggle, onDelete }: Props) {
  function handleDelete() {
    if (window.confirm(`¿Eliminar la plantilla "${template.title}"? Dejará de mostrarse.`)) {
      onDelete()
    }
  }

  return (
    <tr className="border-t border-card-hover transition-colors hover:bg-surface">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <img
            src={template.thumbnail_url || undefined}
            alt=""
            className="h-14 w-10 shrink-0 rounded bg-card-hover object-cover"
          />
          <span className="font-medium text-white">{template.title}</span>
        </div>
      </td>
      <td className="px-4 py-3 tabular-nums text-muted">
        {formatClipDuration(template.duration_seconds)}
      </td>
      <td className="px-4 py-3 text-muted">
        {template.ref_time_s != null ? `${template.ref_time_s} s` : 'Cara más grande'}
      </td>
      <td className="px-4 py-3">
        <span
          className="rounded-full px-2 py-0.5 text-xs font-semibold"
          style={softTone(template.is_active ? '--color-success' : '--text-subdued')}
        >
          {template.is_active ? 'Activa' : 'Inactiva'}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex justify-end gap-0.5">
          <button
            type="button"
            className={BTN_GHOST}
            onClick={onEdit}
            disabled={busy}
            title="Editar"
            aria-label={`Editar ${template.title}`}
          >
            <Pencil size={15} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={BTN_GHOST}
            onClick={onToggle}
            disabled={busy}
            title={template.is_active ? 'Desactivar' : 'Activar'}
            aria-label={`${template.is_active ? 'Desactivar' : 'Activar'} ${template.title}`}
          >
            {template.is_active ? (
              <EyeOff size={15} aria-hidden="true" />
            ) : (
              <Eye size={15} aria-hidden="true" />
            )}
          </button>
          <button
            type="button"
            className={`${BTN_GHOST} hover:!text-error`}
            onClick={handleDelete}
            disabled={busy}
            title="Eliminar"
            aria-label={`Eliminar ${template.title}`}
          >
            <Trash2 size={15} aria-hidden="true" />
          </button>
        </div>
      </td>
    </tr>
  )
}
