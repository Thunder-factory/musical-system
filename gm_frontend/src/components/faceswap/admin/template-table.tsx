import type { ReactNode } from 'react'
import { Clapperboard, RotateCw } from 'lucide-react'

import type { AdminFaceSwapTemplate } from '../../../types/faceswap.types'
import { BTN_OUTLINE } from '../faceswap-ui'
import TemplateRow from './template-row'

interface Props {
  templates: AdminFaceSwapTemplate[]
  isLoading: boolean
  error: string | null
  busyId: string | null
  onRetry: () => void
  onEdit: (template: AdminFaceSwapTemplate) => void
  onToggle: (template: AdminFaceSwapTemplate) => void
  onDelete: (template: AdminFaceSwapTemplate) => void
}

const HEADERS = ['Plantilla', 'Duración', 'Referencia', 'Estado']

function Message({ children }: { children: ReactNode }) {
  return (
    <tr>
      <td colSpan={5} className="px-4 py-10 text-center text-sm text-muted">
        <div className="flex flex-col items-center gap-3">{children}</div>
      </td>
    </tr>
  )
}

/** Tabla de plantillas del admin con estados cargando, error y vacío. */
export default function TemplateTable(props: Props) {
  const { templates, isLoading, error, busyId } = props

  return (
    <div className="overflow-x-auto rounded-lg border border-card-hover">
      <table className="w-full min-w-[520px] text-sm">
        <thead>
          <tr className="bg-card-hover text-xs font-semibold uppercase tracking-wider text-muted">
            {HEADERS.map((h) => (
              <th key={h} className="px-4 py-3 text-left">
                {h}
              </th>
            ))}
            <th className="px-4 py-3 text-right">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <Message>Cargando plantillas…</Message>
          ) : error ? (
            <Message>
              <span style={{ color: 'var(--color-error)' }}>{error}</span>
              <button type="button" className={BTN_OUTLINE} onClick={props.onRetry}>
                <RotateCw size={14} aria-hidden="true" />
                Reintentar
              </button>
            </Message>
          ) : templates.length === 0 ? (
            <Message>
              <Clapperboard size={26} aria-hidden="true" />
              No hay plantillas. Crea la primera con el formulario.
            </Message>
          ) : (
            templates.map((t) => (
              <TemplateRow
                key={t.id}
                template={t}
                busy={busyId === t.id}
                onEdit={() => props.onEdit(t)}
                onToggle={() => props.onToggle(t)}
                onDelete={() => props.onDelete(t)}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
