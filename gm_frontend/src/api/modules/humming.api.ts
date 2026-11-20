import { isAxiosError } from 'axios'

import client from '../client'
import { ENDPOINTS } from '../endpoints'

export type HummingStatus = 'queued' | 'processing' | 'completed' | 'failed'

/** Cuánto de la melodía del tarareo suena en un audio con IA (0-1). */
export interface HummingSimilarity {
  puntaje: number
  nivel: 'alto' | 'medio' | 'bajo'
}

/** Datos del gráfico: todo en segundos del tarareo y semitonos MIDI. */
export interface HummingChart {
  pasoSegundos: number
  /** Altura de la voz cada `pasoSegundos`; null = sin voz. */
  contorno: (number | null)[]
  /** Notas detectadas: [midi, inicio, duración]. */
  notas: [number, number, number][]
  /** Melodía (cuantizada) que sigue la canción: [midi, inicio, duración]. */
  cancion: [number, number, number][]
}

export interface HummingVersion {
  number: number
  style: string | null
  variant: string | null
  score: number | null
  /** Versión de FluidSynth (respaldo si la IA falla). */
  audio_url: string
  midi_url: string | null
  /** La misma versión producida con IA (ACE-Step 1.5), si está activa. */
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
  /** Variantes para escuchar; tras elegir queda solo la elegida. */
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
  // Sin `version`, el backend elige la versión base más parecida al estilo.
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

/** El job sigue "vivo" mientras procesa el tarareo o alguna mejora con IA. */
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
