import type { SelectOption } from '../../../components/ui'

export type CreateMode = 'description' | 'exact_lyrics' | 'auto_lyrics'
export type VocalType = 'male' | 'female' | 'auto'
export type SongLanguage = 'es' | 'en'

export const CREATE_MODE_META: { id: CreateMode; label: string; hint: string }[] = [
  {
    id: 'description',
    label: 'Descripción',
    hint: 'Describe la idea; la IA crea letra y música.',
  },
  {
    id: 'exact_lyrics',
    label: 'Letra exacta',
    hint: 'Usa tu letra; la IA crea la música.',
  },
  {
    id: 'auto_lyrics',
    label: 'Letra IA',
    hint: 'Describe la historia; la IA escribe la letra.',
  },
]

export const DURATION_OPTIONS: SelectOption[] = [
  { value: '40', label: '30–40 seg' },
  { value: '60', label: '1 min' },
  { value: '150', label: '2:30+ min' },
]

export const VOCAL_OPTIONS: SelectOption[] = [
  { value: 'auto', label: 'Automática' },
  { value: 'female', label: 'Voz femenina' },
  { value: 'male', label: 'Voz masculina' },
]

export const LANGUAGE_OPTIONS: SelectOption[] = [
  { value: 'es', label: 'Español' },
  { value: 'en', label: 'Inglés' },
]
