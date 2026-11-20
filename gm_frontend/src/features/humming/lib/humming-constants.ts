import type { HummingFidelity } from '../api/humming.api'

export const MIN_HUMMING_SECONDS = 8
export const MAX_HUMMING_SECONDS = 30
export const HUMMING_CREDIT_COST = 1
export const CUSTOM_HUMMING_STYLE = 'custom'

export const FIDELITY_LABELS: Record<HummingFidelity, { label: string; hint: string }> = {
  alta: { label: 'Alta', hint: 'Respeta mucho tu melodía; cambia menos el sonido.' },
  media: { label: 'Media', hint: 'Equilibrio entre tu melodía y el estilo elegido.' },
  libre: { label: 'Libre', hint: 'Cambia más el estilo; la melodía puede variar.' },
}

export const STYLE_LABELS: Record<string, string> = {
  pop: 'Pop',
  folk: 'Folk',
  balada: 'Balada',
  lofi: 'Lo-fi',
  rock_suave: 'Rock suave',
  epico: 'Épico',
  electronico: 'Electrónico',
}

export const STAGE_LABELS: Record<string, string> = {
  ingesta: 'Preparando tu grabación…',
  preprocesado: 'Limpiando el audio…',
  melodia: 'Detectando tu melodía…',
  limpieza: 'Afinando las notas…',
  analisis: 'Analizando ritmo y tonalidad…',
  armonia: 'Armando los acordes…',
  estilo: 'Eligiendo el estilo…',
  arreglo: 'Arreglando los instrumentos…',
  render: 'Grabando la versión principal…',
  'version-1-lista': 'Versión principal lista…',
  'alternativa-2': 'Creando una versión alternativa…',
  'version-2-lista': 'Segunda versión lista…',
  'alternativa-3': 'Creando otra versión alternativa…',
  'version-3-lista': 'Tercera versión lista…',
  subida: 'Guardando tus canciones…',
  completado: 'Listo',
}

export const STATUS_LABELS: Record<string, string> = {
  queued: 'En cola',
  processing: 'Procesando',
  completed: 'Listo',
  failed: 'Error',
}

export function styleLabel(style: string | null | undefined): string {
  if (!style) {
    return 'Versión'
  }
  return STYLE_LABELS[style] ?? style
}

export function formatSeconds(seconds: number): string {
  const whole = Math.floor(seconds)
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`
}
