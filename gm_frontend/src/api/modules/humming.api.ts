import { isAxiosError } from 'axios'

import client from '../client'
import { ENDPOINTS } from '../endpoints'

export type HummingStatus = 'queued' | 'processing' | 'completed' | 'failed'

export interface HummingVersion {
  number: number
  style: string | null
  variant: string | null
  score: number | null
  audio_url: string
  midi_url: string | null
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
