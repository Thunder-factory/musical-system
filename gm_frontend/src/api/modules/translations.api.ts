import { isAxiosError } from 'axios'

import client from '../client'
import { ENDPOINTS } from '../endpoints'

export type TranslationStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type TranslationFileKind = 'video' | 'audio'

export interface TranslationLanguage {
  code: string
  label: string
}

export interface TranslationConfig {
  languages: TranslationLanguage[]
  allowed_extensions: string[]
  max_duration_seconds: number
  max_file_size_mb: number
  credit_cost: number
}

export interface LyricPhrase {
  inicio: number
  fin: number
  texto: string
  /** No llega cuando la letra original proviene de LRCLIB. */
  original?: string
  conservar?: boolean
}

export interface TranslationLyrics {
  idioma_origen: string
  idioma_destino: string
  modelo?: string
  fuente_letra?: 'usuario' | 'lrclib' | 'whisper'
  resumen?: string
  titulo?: string
  artista?: string
  frases: LyricPhrase[]
}

export interface TranslationJob {
  id: string
  source_filename: string
  source_file_size_bytes: number
  source_duration_seconds: number | null
  target_language: string
  song_title: string
  song_artist: string
  remote_job_id: string | null
  mode: string
  status: TranslationStatus
  stage: string
  progress_pct: number
  credits_used: number
  error_message: string | null
  lyrics: TranslationLyrics | null
  details: Record<string, unknown>
  has_video: boolean
  has_audio: boolean
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface CreateTranslationInput {
  file: File
  targetLanguage: string
  title?: string
  artist?: string
  onUploadProgress?: (percent: number) => void
}

export async function getTranslationConfig(): Promise<TranslationConfig> {
  const { data } = await client.get(ENDPOINTS.translations.config)
  return data
}

export async function createTranslation({
  file,
  targetLanguage,
  title,
  artist,
  onUploadProgress,
}: CreateTranslationInput): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('target_language', targetLanguage)
  if (title?.trim()) {form.append('title', title.trim())}
  if (artist?.trim()) {form.append('artist', artist.trim())}

  const { data } = await client.post(ENDPOINTS.translations.create, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
    onUploadProgress: (event) => {
      if (onUploadProgress && event.total) {
        onUploadProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return data
}

export async function getTranslationJobs(): Promise<TranslationJob[]> {
  const { data } = await client.get(ENDPOINTS.translations.jobs)
  return data
}

export async function getTranslationJob(jobId: string): Promise<TranslationJob> {
  const { data } = await client.get(ENDPOINTS.translations.jobStatus(jobId))
  return data
}

export async function getTranslationFileUrl(
  jobId: string,
  file: TranslationFileKind,
  download = false,
): Promise<string> {
  const { data } = await client.get(ENDPOINTS.translations.downloadUrl(jobId), {
    params: { file, ...(download ? { download: '1' } : {}) },
  })
  return data.url
}

export function getTranslationErrorMessage(error: unknown): string {
  if (!isAxiosError(error)) {
    return 'No se pudo iniciar la traducción.'
  }
  if (error.response?.status === 402) {
    return 'No tienes créditos suficientes para traducir este video.'
  }
  const data = error.response?.data as { detail?: string; error?: string } | undefined
  return data?.detail ?? data?.error ?? 'No se pudo iniciar la traducción.'
}
