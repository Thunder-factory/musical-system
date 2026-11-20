import { isAxiosError } from 'axios'

import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'

export type HummingStatus = 'queued' | 'processing' | 'completed' | 'failed'

export interface HummingSimilarity {
  puntaje: number
  nivel: 'alto' | 'medio' | 'bajo'
}

export interface HummingChart {
  pasoSegundos: number
  contorno: (number | null)[]
  notas: [number, number, number][]
  cancion: [number, number, number][]
}

export interface HummingVersion {
  number: number
  style: string | null
  variant: string | null
  score: number | null
  audio_url: string
  midi_url: string | null
  ai: {
    status: HummingStatus
    audio_url: string | null
    cover_url: string | null
    similarity: HummingSimilarity | null
  } | null
}

export interface HummingMetadata {
  bpm?: number
  tonalidad?: string
  acordes?: string[]
  estilo?: string
  estiloMensaje?: string
  estiloAmbiguo?: boolean
  duracionCancionSegundos?: number
  motivo?: string
  grafico?: HummingChart | null
}

export type HummingFidelity = 'alta' | 'media' | 'libre'

export interface HummingEnhancement {
  id: string
  version_number: number
  style_key: string
  style_label: string
  fidelity: HummingFidelity
  status: HummingStatus
  progress: number
  error_message: string | null
  credits_used: number
  variants: { number: number; audio_url: string; similarity: HummingSimilarity | null }[]
  chosen_variant: number | null
  song_id: string | null
  cover_url: string | null
  created_at: string
  completed_at: string | null
}

export interface HummingStyle {
  key: string
  label: string
  group: string
  experimental: boolean
}

export interface HummingStylesCatalog {
  styles: HummingStyle[]
  fidelities: HummingFidelity[]
  credit_cost: number
  available: boolean
}

export interface HummingJob {
  id: string
  title: string
  status: HummingStatus
  progress: number
  stage: string
  error_message: string | null
  error_code: string
  metadata: HummingMetadata
  versions: HummingVersion[]
  downloads: {
    melody_midi_url?: string | null
    score_musicxml_url?: string | null
  }
  chosen_version: number | null
  song_id: string | null
  enhancements: HummingEnhancement[]
  credits_used: number
  created_at: string
  completed_at: string | null
}

export const HUMMING_FINAL_STATES: HummingStatus[] = ['completed', 'failed']

export async function uploadHumming(file: File, title?: string): Promise<HummingJob> {
  const form = new FormData()
  form.append('file', file)
  if (title?.trim()) {
    form.append('title', title.trim())
  }
  const { data } = await client.post<HummingJob>(ENDPOINTS.humming.list, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getHummingJobs(): Promise<HummingJob[]> {
  const { data } = await client.get<HummingJob[] | { results: HummingJob[] }>(
    ENDPOINTS.humming.list
  )
  return Array.isArray(data) ? data : data.results
}

export async function getHummingJob(jobId: string): Promise<HummingJob> {
  const { data } = await client.get<HummingJob>(ENDPOINTS.humming.detail(jobId))
  return data
}

export async function chooseHummingVersion(
  jobId: string,
  version: number,
  title?: string
): Promise<{ id: string; title: string }> {
  const { data } = await client.post(ENDPOINTS.humming.choose(jobId), {
    version,
    ...(title?.trim() ? { title: title.trim() } : {}),
  })
  return data
}

export async function getHummingStyles(): Promise<HummingStylesCatalog> {
  const { data } = await client.get<HummingStylesCatalog>(ENDPOINTS.humming.styles)
  return data
}

export async function enhanceHumming(
  jobId: string,
  body: { version?: number; style: string; custom_style?: string; fidelity: HummingFidelity }
): Promise<HummingEnhancement> {
  const { data } = await client.post<HummingEnhancement>(ENDPOINTS.humming.enhance(jobId), body)
  return data
}

export async function chooseEnhancementVariant(
  enhancementId: string,
  variant: number
): Promise<{ id: string; title: string }> {
  const { data } = await client.post(ENDPOINTS.humming.chooseEnhancement(enhancementId), {
    variant,
  })
  return data
}

export function isHummingJobActive(job: HummingJob): boolean {
  return (
    !HUMMING_FINAL_STATES.includes(job.status) ||
    job.versions.some((v) => v.ai && !HUMMING_FINAL_STATES.includes(v.ai.status)) ||
    job.enhancements.some((item) => !HUMMING_FINAL_STATES.includes(item.status))
  )
}

export function isNoCreditsError(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 402
}

export function getHummingErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) {
    return fallback
  }
  const data = error.response?.data as { detail?: string } | undefined
  return data?.detail ?? fallback
}
