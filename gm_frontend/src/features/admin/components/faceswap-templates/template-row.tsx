import { Eye, EyeOff, Pencil, Trash2 } from 'lucide-react'

import { Badge, useConfirm } from '../../../../components/ui'
import type { AdminFaceSwapTemplate } from '../../../faceswap/types/faceswap.types'
import { formatClipDuration } from './template-validation'

interface Props {
  template: AdminFaceSwapTemplate
  busy: boolean
  onEdit: () => void
  onToggle: () => void
  onDelete: () => void
}

const ACTION_BTN =
  'inline-flex h-8 w-8 items-center justify-center rounded-md text-muted transition-colors hover:bg-card-hover hover:text-white disabled:cursor-not-allowed disabled:opacity-40'

export default function TemplateRow({ template, busy, onEdit, onToggle, onDelete }: Props) {
  const confirm = useConfirm()

  async function handleDelete() {
    const accepted = await confirm({
      title: '¿Eliminar plantilla?',
      description: `Se eliminará "${template.title}" y dejará de estar disponible para los usuarios.`,
      confirmLabel: 'Eliminar',
      variant: 'danger',
    })
    if (accepted) {
      onDelete()
    }
  }

  return (
    <tr className="border-t border-border transition-colors hover:bg-surface">
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
        <Badge variant={template.is_active ? 'success' : 'neutral'}>
          {template.is_active ? 'Activa' : 'Inactiva'}
        </Badge>
      </td>
      <td className="px-4 py-3">
        <div className="flex justify-end gap-1">
          <button
            type="button"
            className={ACTION_BTN}
            onClick={onEdit}
            disabled={busy}
            title="Editar"
            aria-label={`Editar ${template.title}`}
          >
            <Pencil size={15} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={ACTION_BTN}
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
            className={`${ACTION_BTN} hover:bg-error-soft hover:text-error`}
            onClick={() => void handleDelete()}
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
