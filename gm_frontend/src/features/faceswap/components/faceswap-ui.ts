import type { CSSProperties } from 'react'

import type { FaceSwapStatus } from '../types/faceswap.types'

export const BTN_PRIMARY =
  'inline-flex items-center justify-center gap-2 rounded-pill bg-primary px-6 py-3 text-sm ' +
  'font-bold text-black transition-all duration-200 hover:scale-[1.02] hover:bg-primary-light ' +
  'disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100 ' +
  'disabled:hover:bg-primary'

export const BTN_OUTLINE =
  'inline-flex items-center justify-center gap-2 rounded-pill border border-border-strong ' +
  'px-4 py-2 text-sm font-semibold text-white transition-colors hover:border-primary ' +
  'hover:text-primary disabled:cursor-not-allowed disabled:opacity-50'

export const BTN_GHOST =
  'inline-flex items-center justify-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs ' +
  'font-medium text-muted transition-colors hover:bg-card-hover hover:text-white ' +
  'disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent'

export const INPUT =
  'w-full rounded bg-card-hover px-3 py-2 text-sm font-normal text-white border ' +
  'border-transparent focus:border-primary focus-visible:outline-2 placeholder:text-muted disabled:opacity-60'

export const FILE_INPUT =
  `${INPUT} file:mr-3 file:rounded-pill file:border-0 file:bg-surface file:px-3 file:py-1 ` +
  'file:text-white'

export function softTone(colorVar: string): CSSProperties {
  return {
    color: `var(${colorVar})`,
    background: `color-mix(in srgb, var(${colorVar}) 12%, transparent)`,
    border: `1px solid color-mix(in srgb, var(${colorVar}) 25%, transparent)`,
  }
}

export const STATUS_META: Record<FaceSwapStatus, { label: string; colorVar: string }> = {
  queued: { label: 'En cola', colorVar: '--color-warning' },
  processing: { label: 'Procesando', colorVar: '--color-warning' },
  completed: { label: 'Completado', colorVar: '--color-success' },
  failed: { label: 'Error', colorVar: '--color-error' },
}

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

export function formatFileSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
