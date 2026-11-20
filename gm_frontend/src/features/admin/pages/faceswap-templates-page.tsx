import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { toast } from '../../../store/toast.store'
import {
  createAdminTemplate,
  deleteAdminTemplate,
  getAdminTemplates,
  getFaceSwapErrorMessage,
  updateAdminTemplate,
} from '../../faceswap/api/faceswap.api'
import type { AdminFaceSwapTemplate, TemplateFormValues } from '../../faceswap/types/faceswap.types'
import TemplateForm from '../components/faceswap-templates/template-form'
import TemplateKpis from '../components/faceswap-templates/template-kpis'
import TemplateTable from '../components/faceswap-templates/template-table'

const QUERY_KEY = ['admin-faceswap-templates']

export default function FaceSwapTemplatesPage() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: QUERY_KEY, queryFn: getAdminTemplates })
  const templates = query.data ?? []
  const [editing, setEditing] = useState<AdminFaceSwapTemplate | null>(null)
  const [formKey, setFormKey] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: QUERY_KEY })

  function startEdit(template: AdminFaceSwapTemplate | null) {
    setEditing(template)
    setFormError(null)
    setFormKey((k) => k + 1)
  }

  async function save(values: TemplateFormValues) {
    setSubmitting(true)
    setFormError(null)
    try {
      await (editing ? updateAdminTemplate(editing.id, values) : createAdminTemplate(values))
      toast.success(editing ? 'Plantilla actualizada' : 'Plantilla creada')
      startEdit(null)
      await refresh()
    } catch (err: unknown) {
      setFormError(getFaceSwapErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function runAction(
    template: AdminFaceSwapTemplate,
    action: () => Promise<unknown>,
    successMsg: string
  ) {
    setBusyId(template.id)
    setActionError(null)
    try {
      await action()
      if (editing?.id === template.id) {
        startEdit(null)
      }
      toast.success(successMsg)
      await refresh()
    } catch (err: unknown) {
      const msg = getFaceSwapErrorMessage(err)
      setActionError(msg)
      toast.error(msg)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6 text-white">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Plantillas de video</h1>
        <p className="mt-1 text-sm text-muted">
          Catálogo de videos base que los usuarios pueden usar en Cambiar caras.
        </p>
      </header>

      <TemplateKpis templates={templates} />

      <div className="grid items-start gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <TemplateForm
          key={formKey}
          initial={editing}
          submitting={submitting}
          error={formError}
          onSubmit={(values) => void save(values)}
          onCancel={() => startEdit(null)}
        />
        <div className="flex min-w-0 flex-col gap-2">
          {actionError && (
            <p className="text-sm text-error" role="alert">
              {actionError}
            </p>
          )}
          <TemplateTable
            templates={templates}
            isLoading={query.isLoading}
            error={query.isError ? getFaceSwapErrorMessage(query.error) : null}
            busyId={busyId}
            onRetry={() => void query.refetch()}
            onEdit={startEdit}
            onToggle={(t) =>
              void runAction(
                t,
                () => updateAdminTemplate(t.id, { is_active: !t.is_active }),
                t.is_active ? 'Plantilla desactivada' : 'Plantilla activada'
              )
            }
            onDelete={(t) =>
              void runAction(t, () => deleteAdminTemplate(t.id), 'Plantilla eliminada')
            }
          />
        </div>
      </div>
    </div>
  )
}
