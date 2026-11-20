import type { TranslationConfig } from '../api/translations.api'

export const LANGUAGE_NAMES: Record<string, string> = {
  en: 'Inglés',
  es: 'Español',
  fr: 'Francés',
  zh: 'Chino',
}

export const TRANSLATION_STAGES: { key: string; label: string }[] = [
  { key: 'descargando', label: 'Preparando video' },
  { key: 'extrayendo', label: 'Extrayendo audio' },
  { key: 'separando', label: 'Separando la voz' },
  { key: 'transcribiendo', label: 'Transcribiendo letra' },
  { key: 'traduciendo', label: 'Traduciendo y adaptando' },
  { key: 'sintetizando', label: 'Generando nueva voz' },
  { key: 'mezclando', label: 'Mezclando con el video' },
  { key: 'subiendo', label: 'Guardando resultado' },
]

const EXTRA_STAGE_LABELS: Record<string, string> = {
  subiendo_video: 'Subiendo tu video…',
  en_cola: 'En cola…',
  completado: 'Completado',
}

export const TRANSLATION_STATUS_LABELS: Record<string, string> = {
  queued: 'En cola',
  processing: 'Procesando',
  completed: 'Completado',
  failed: 'Error',
}

export const DEFAULT_TRANSLATION_CONFIG: TranslationConfig = {
  languages: Object.entries(LANGUAGE_NAMES).map(([code, label]) => ({ code, label })),
  allowed_extensions: ['.mp4', '.mov', '.webm'],
  max_duration_seconds: 300,
  max_file_size_mb: 300,
  credit_cost: 3,
}

export function stageLabel(stage: string): string {
  return (
    TRANSLATION_STAGES.find((s) => s.key === stage)?.label ?? EXTRA_STAGE_LABELS[stage] ?? stage
  )
}

export function formatFileSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatDuration(total: number | null | undefined): string {
  if (total == null || Number.isNaN(total)) {
    return '—'
  }
  const minutes = Math.floor(total / 60)
  const seconds = Math.floor(total % 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

export function readVideoDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const video = document.createElement('video')
    video.preload = 'metadata'
    const done = (value: number | null) => {
      URL.revokeObjectURL(url)
      resolve(value)
    }
    video.onloadedmetadata = () => done(Number.isFinite(video.duration) ? video.duration : null)
    video.onerror = () => done(null)
    video.src = url
  })
}
