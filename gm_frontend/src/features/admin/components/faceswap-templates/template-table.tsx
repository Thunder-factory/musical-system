import type { ReactNode } from 'react'
import { Clapperboard, RotateCw } from 'lucide-react'

import { Button } from '../../../../components/ui'
import type { AdminFaceSwapTemplate } from '../../../faceswap/types/faceswap.types'
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

export default function TemplateTable(props: Props) {
  const { templates, isLoading, error, busyId } = props

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
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
            <Message>Cargando plantillas...</Message>
          ) : error ? (
            <Message>
              <span className="text-error">{error}</span>
              <Button variant="secondary" size="sm" leftIcon={<RotateCw size={14} />} onClick={props.onRetry}>
                Reintentar
              </Button>
            </Message>
          ) : templates.length === 0 ? (
            <Message>
              <Clapperboard size={26} aria-hidden="true" />
              <span>No hay plantillas. Crea la primera con el formulario.</span>
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
