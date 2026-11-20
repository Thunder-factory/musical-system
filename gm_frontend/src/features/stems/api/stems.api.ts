import { isAxiosError } from 'axios'

import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'

export const STEM_CREDIT_COST = 2

export interface StemFile {
  id: string
  stem_type: 'vocals' | 'no_vocals' | 'bass' | 'drums' | 'other'
  duration_seconds: number | null
  file_size_bytes: number | null
  created_at: string
}

export interface StemJob {
  id: string
  remote_job_id?: string | null
  source_filename: string
  source_file_size_bytes: number
  model_used?: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress_pct: number
  credits_used: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  stem_files?: StemFile[]
}

export async function uploadAndSeparate(file: File): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<{ job_id: string }>(ENDPOINTS.stems.separate, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function separateFromSong(songId: string): Promise<{ job_id: string }> {
  const { data } = await client.post<{ job_id: string }>(ENDPOINTS.stems.separate, {
    song_id: songId,
  })
  return data
}

export function isStemNoCreditsError(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 402
}

export function getStemErrorMessage(error: unknown): string {
  if (!isAxiosError(error)) {
    return 'Error al iniciar la separación.'
  }
  const data = error.response?.data as { detail?: string; error?: string } | undefined
  return data?.detail ?? data?.error ?? 'Error al iniciar la separación.'
}

export async function getStemJobs(): Promise<StemJob[]> {
  const { data } = await client.get<StemJob[]>(ENDPOINTS.stems.jobs)
  return data
}

export async function getStemJobStatus(jobId: string): Promise<StemJob> {
  const { data } = await client.get<StemJob>(ENDPOINTS.stems.jobStatus(jobId))
  return data
}

export async function getStemDownloadUrl(fileId: string, download = false): Promise<string> {
  const { data } = await client.get<{ url: string }>(ENDPOINTS.stems.downloadUrl(fileId), {
    params: download ? { download: '1' } : undefined,
  })
  return data.url
}
