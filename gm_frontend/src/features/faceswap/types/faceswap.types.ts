export type FaceSwapStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type FaceSwapSourceType = 'template' | 'upload'
export type FaceSwapSourceMode = 'catalog' | 'own'

export interface FaceSwapTemplate {
  id: string
  title: string
  duration_seconds: number
  has_reference: boolean
  thumbnail_url: string
  preview_url: string
}

export interface AdminFaceSwapTemplate extends FaceSwapTemplate {
  ref_time_s: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface FaceSwapJob {
  id: string
  source_type: FaceSwapSourceType
  template: { id: string; title: string } | null
  source_video_filename: string
  source_duration_seconds: number | null
  model_used: string
  remote_job_id: string | null
  status: FaceSwapStatus
  progress_pct: number
  credits_used: number
  error_message: string | null
  has_result: boolean
  ref_time_s: number | null
  target_face_x: number | null
  target_face_y: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface FaceTarget {
  ref_time_s: number
  face_x: number
  face_y: number
}

export interface CreateFaceSwapJobInput {
  photo: File
  consent: boolean
  templateId?: string
  video?: File
  target?: FaceTarget
}

export interface FaceSwapJobCreated {
  job_id: string
  status: FaceSwapStatus
}

export interface TemplateFormValues {
  title: string
  refTimeS: number | null
  isActive: boolean
  video?: File
  thumbnail?: File
}

export const FACESWAP_CREDIT_COST = 3
export const FACESWAP_MAX_SECONDS = 15
export const FACESWAP_MAX_PHOTO_MB = 8
export const FACESWAP_MAX_VIDEO_MB = 50

export const FACESWAP_ACTIVE_STATUSES: FaceSwapStatus[] = ['queued', 'processing']

export function formatClipDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) {
    return '0:00'
  }
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, '0')}`
}
