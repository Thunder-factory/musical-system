import { isAxiosError } from 'axios'

import client from '../client'
import { ENDPOINTS } from '../endpoints'
import type {
  AdminFaceSwapTemplate,
  CreateFaceSwapJobInput,
  FaceSwapJob,
  FaceSwapJobCreated,
  FaceSwapTemplate,
  TemplateFormValues,
} from '../../types/faceswap.types'

const MULTIPART = { headers: { 'Content-Type': 'multipart/form-data' } }

// ── Usuario ─────────────────────────────────────────────────────────────

export async function getFaceSwapTemplates(): Promise<FaceSwapTemplate[]> {
  const { data } = await client.get<FaceSwapTemplate[]>(ENDPOINTS.faceswap.templates)
  return data
}

export async function createFaceSwapJob(
  input: CreateFaceSwapJobInput
): Promise<FaceSwapJobCreated> {
  const form = new FormData()
  form.append('photo', input.photo)
  form.append('consent', input.consent ? 'true' : 'false')
  if (input.templateId) {
    form.append('template_id', input.templateId)
  }
  if (input.video) {
    form.append('video', input.video)
  }
  const { data } = await client.post<FaceSwapJobCreated>(ENDPOINTS.faceswap.jobs, form, MULTIPART)
  return data
}

export async function getFaceSwapJobs(): Promise<FaceSwapJob[]> {
  const { data } = await client.get<FaceSwapJob[]>(ENDPOINTS.faceswap.jobs)
  return data
}

export async function getFaceSwapJob(id: string): Promise<FaceSwapJob> {
  const { data } = await client.get<FaceSwapJob>(ENDPOINTS.faceswap.job(id))
  return data
}

export async function deleteFaceSwapJob(id: string): Promise<void> {
  await client.delete(ENDPOINTS.faceswap.job(id))
}

export async function getFaceSwapResultUrl(id: string, download = false): Promise<string> {
  const { data } = await client.get<{ url: string }>(ENDPOINTS.faceswap.resultUrl(id), {
    params: download ? { download: '1' } : undefined,
  })
  return data.url
}

// ── Admin ───────────────────────────────────────────────────────────────

function templateForm(values: TemplateFormValues): FormData {
  const form = new FormData()
  form.append('title', values.title.trim())
  form.append('ref_time_s', values.refTimeS == null ? '' : String(values.refTimeS))
  form.append('is_active', values.isActive ? 'true' : 'false')
  if (values.video) {
    form.append('video', values.video)
  }
  if (values.thumbnail) {
    form.append('thumbnail', values.thumbnail)
  }
  return form
}

export async function getAdminTemplates(): Promise<AdminFaceSwapTemplate[]> {
  const { data } = await client.get<AdminFaceSwapTemplate[]>(ENDPOINTS.faceswap.adminTemplates)
  return data
}

export async function createAdminTemplate(
  values: TemplateFormValues
): Promise<AdminFaceSwapTemplate> {
  const { data } = await client.post<AdminFaceSwapTemplate>(
    ENDPOINTS.faceswap.adminTemplates,
    templateForm(values),
    MULTIPART
  )
  return data
}

/** PATCH multipart. Para cambiar solo `is_active` se puede pasar un objeto parcial (JSON). */
export async function updateAdminTemplate(
  id: string,
  values: TemplateFormValues | { is_active: boolean }
): Promise<AdminFaceSwapTemplate> {
  const isPartial = !('title' in values)
  const { data } = await client.patch<AdminFaceSwapTemplate>(
    ENDPOINTS.faceswap.adminTemplate(id),
    isPartial ? values : templateForm(values),
    isPartial ? undefined : MULTIPART
  )
  return data
}

export async function deleteAdminTemplate(id: string): Promise<void> {
  await client.delete(ENDPOINTS.faceswap.adminTemplate(id))
}

// ── Errores ─────────────────────────────────────────────────────────────

export function getFaceSwapErrorMessage(error: unknown): string {
  if (!isAxiosError(error)) {
    return 'Ocurrió un error inesperado.'
  }
  if (!error.response) {
    return 'No se pudo conectar con el servidor. Revisa tu conexión.'
  }
  const data = error.response.data as Record<string, unknown> | string | undefined
  if (data && typeof data === 'object') {
    if (typeof data.error === 'string') {
      return data.error
    }
    if (typeof data.detail === 'string') {
      return data.detail
    }
    // Errores de serializer DRF: { campo: ["mensaje"] }
    const first = Object.values(data)
      .flat()
      .find((v) => typeof v === 'string')
    if (typeof first === 'string') {
      return first
    }
  }
  if (error.response.status === 404) {
    return 'El servicio de Cambiar caras no está disponible por ahora.'
  }
  return 'Error al procesar la solicitud.'
}

export function isNoCreditsError(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 402
}
