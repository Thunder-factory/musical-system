import {
  FACESWAP_MAX_PHOTO_MB,
  FACESWAP_MAX_SECONDS,
  FACESWAP_MAX_VIDEO_MB,
} from '../types/faceswap.types'
import { fileExtension } from './faceswap-ui'

const PHOTO_EXTS = ['.jpg', '.jpeg', '.png', '.webp']
const VIDEO_EXTS = ['.mp4', '.mov', '.webm']
const MB = 1024 * 1024

export const PHOTO_ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'
export const VIDEO_ACCEPT = '.mp4,.mov,.webm,video/mp4,video/quicktime,video/webm'

export function validatePhoto(file: File): string | null {
  if (!PHOTO_EXTS.includes(fileExtension(file.name))) {
    return 'Solo se aceptan fotos JPG, PNG o WEBP.'
  }
  if (file.size === 0) {
    return 'La foto está vacía.'
  }
  if (file.size > FACESWAP_MAX_PHOTO_MB * MB) {
    return `La foto excede el límite de ${FACESWAP_MAX_PHOTO_MB} MB.`
  }
  return null
}

function readDuration(file: File): Promise<number> {
  const url = URL.createObjectURL(file)
  return new Promise<number>((resolve) => {
    const probe = document.createElement('video')
    probe.preload = 'metadata'
    probe.onloadedmetadata = () => resolve(probe.duration)
    probe.onerror = () => resolve(Number.NaN)
    probe.src = url
  }).finally(() => URL.revokeObjectURL(url))
}

export async function validateClip(
  file: File
): Promise<{ error: string | null; duration: number | null }> {
  if (!VIDEO_EXTS.includes(fileExtension(file.name))) {
    return { error: 'Solo se aceptan videos MP4, MOV o WEBM.', duration: null }
  }
  if (file.size > FACESWAP_MAX_VIDEO_MB * MB) {
    return { error: `El video excede el límite de ${FACESWAP_MAX_VIDEO_MB} MB.`, duration: null }
  }
  const seconds = await readDuration(file)
  if (Number.isFinite(seconds) && seconds > FACESWAP_MAX_SECONDS + 0.5) {
    return {
      error: `El video debe durar como máximo ${FACESWAP_MAX_SECONDS} segundos.`,
      duration: seconds,
    }
  }
  return { error: null, duration: Number.isFinite(seconds) ? seconds : null }
}

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
