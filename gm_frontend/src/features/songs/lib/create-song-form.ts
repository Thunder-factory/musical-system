import type { GenerateSongPayload } from '../api/songs.api'
import type { CreateMode, SongLanguage, VocalType } from './create-song-options'

export interface CreateFormValues {
  mode: CreateMode
  title: string
  description: string
  prompt: string
  lyrics: string
  describedLyrics: string
  selectedTagValues: string[]
  duration: number
  vocalType: VocalType
  language: SongLanguage
  guidanceScale: number
  inferStep: number
}

export function validateCreateForm(values: CreateFormValues): string | null {
  if (!values.title.trim()) {
    return 'El título es obligatorio.'
  }
  if (values.mode === 'description' && !values.description.trim()) {
    return 'Describe qué quieres escuchar en tu canción.'
  }
  if (values.mode === 'exact_lyrics') {
    if (!values.prompt.trim() && values.selectedTagValues.length === 0) {
      return 'Especifica el estilo musical o selecciona una etiqueta.'
    }
    if (!values.lyrics.trim()) {
      return 'Escribe la letra exacta de la canción.'
    }
  }
  if (values.mode === 'auto_lyrics') {
    if (!values.prompt.trim() && values.selectedTagValues.length === 0) {
      return 'Especifica el estilo musical o selecciona una etiqueta.'
    }
    if (!values.describedLyrics.trim()) {
      return 'Describe de qué trata la canción.'
    }
  }
  return null
}

export function buildCreateSongPayload(values: CreateFormValues): GenerateSongPayload {
  const tagsStr = values.selectedTagValues.join(', ')
  const base: GenerateSongPayload = {
    title: values.title.trim(),
    audio_duration: values.duration,
    instrumental: false,
    vocal_type: values.vocalType,
    language: values.language,
    guidance_scale: values.guidanceScale,
    infer_step: values.inferStep,
  }
  if (values.mode === 'description') {
    const fullDesc = tagsStr
      ? `${tagsStr}. ${values.description.trim()}`.trim()
      : values.description.trim()
    return { ...base, description: fullDesc }
  }
  const fullPrompt =
    tagsStr && values.prompt.trim()
      ? `${tagsStr}, ${values.prompt.trim()}`
      : tagsStr || values.prompt.trim()

  if (values.mode === 'exact_lyrics') {
    return { ...base, prompt: fullPrompt, lyrics: values.lyrics.trim() }
  }
  return { ...base, prompt: fullPrompt, described_lyrics: values.describedLyrics.trim() }
}
