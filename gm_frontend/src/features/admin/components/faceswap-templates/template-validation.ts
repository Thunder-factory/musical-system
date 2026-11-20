export const PHOTO_ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'
export const VIDEO_ACCEPT = '.mp4,.mov,.webm,video/mp4,video/quicktime,video/webm'

export function validateTemplateForm(opts: {
  title: string
  refTimeS: number | null
  needsVideo: boolean
  maxSeconds?: number
}): string | null {
  const title = opts.title.trim()
  if (!title || title.length > 120) {
    return 'El título debe tener entre 1 y 120 caracteres.'
  }
  if (opts.needsVideo) {
    return 'Elige el video de la plantilla.'
  }
  const max = opts.maxSeconds ?? Number.POSITIVE_INFINITY
  const ref = opts.refTimeS
  if (ref != null && (!Number.isFinite(ref) || ref < 0 || ref > max)) {
    return 'El segundo de referencia está fuera del video.'
  }
  return null
}

export function formatClipDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) {
    return '0:00'
  }
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, '0')}`
}
