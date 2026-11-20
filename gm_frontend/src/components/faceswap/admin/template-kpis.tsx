import type { AdminFaceSwapTemplate } from '../../../types/faceswap.types'

interface Props {
  templates: AdminFaceSwapTemplate[]
}

/** KPIs mínimos del catálogo: total, activas e inactivas. */
export default function TemplateKpis({ templates }: Props) {
  const active = templates.filter((t) => t.is_active).length
  const items = [
    { label: 'Total', value: templates.length },
    { label: 'Activas', value: active },
    { label: 'Inactivas', value: templates.length - active },
  ]

  return (
    <div className="grid grid-cols-3 gap-3">
      {items.map((item) => (
        <div key={item.label} className="rounded-lg bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">{item.label}</p>
          <p className="mt-1 text-2xl font-bold tabular-nums text-white">{item.value}</p>
        </div>
      ))}
    </div>
  )
}
