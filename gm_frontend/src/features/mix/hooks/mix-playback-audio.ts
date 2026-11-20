import { getSongPlayUrl } from '../../songs/api/songs.api'
import { getStemDownloadUrl } from '../../stems/api/stems.api'
import { getMixClipPlayUrl, type MixClip } from '../api/mix.api'

export type PlaybackMode = 'global' | 'individual'
export type PlaybackState = 'idle' | 'playing' | 'paused'

export const clampVolume = (volume: number) => Math.max(0, Math.min(volume, 2))

export function recordsEqual(
  first: Record<string, boolean>,
  second: Record<string, boolean>
): boolean {
  const firstKeys = Object.keys(first).filter((k) => first[k])
  const secondKeys = Object.keys(second).filter((k) => second[k])
  return firstKeys.length === secondKeys.length && firstKeys.every((k) => second[k] === true)
}

export function isClipAudible(
  clip: MixClip,
  mode: PlaybackMode,
  muted: Record<string, boolean>,
  solo: Record<string, boolean>
): boolean {
  if (muted[clip.id]) {
    return false
  }
  if (mode === 'individual') {
    return true
  }
  const soloIds = Object.keys(solo).filter((id) => solo[id])
  return soloIds.length === 0 || Boolean(solo[clip.id])
}

export function applyClipVolume(
  clip: MixClip,
  audio: HTMLAudioElement,
  gainNode: GainNode | undefined,
  positionMs: number,
  mode: PlaybackMode,
  muted: Record<string, boolean>,
  solo: Record<string, boolean>
) {
  if (!isClipAudible(clip, mode, muted, solo)) {
    if (gainNode) {
      gainNode.gain.value = 0
    } else {
      audio.volume = 0
    }
    return
  }
  const elapsedMs = positionMs - clip.timeline_start_ms
  const remainingMs = clip.duration_ms - elapsedMs
  const fadeIn = clip.fade_in_ms > 0 ? Math.min(1, elapsedMs / clip.fade_in_ms) : 1
  const fadeOut = clip.fade_out_ms > 0 ? Math.min(1, remainingMs / clip.fade_out_ms) : 1
  const targetGain = clampVolume(clip.volume) * Math.max(0, Math.min(fadeIn, fadeOut))
  if (gainNode) {
    gainNode.gain.value = targetGain
    audio.volume = 1
  } else {
    audio.volume = Math.min(targetGain, 1)
  }
}

export async function fetchClipAudioUrl(
  clip: MixClip,
  mixId: string | undefined,
  urlCache: Map<string, string>
): Promise<string> {
  const cached = urlCache.get(clip.id)
  if (cached) {
    return cached
  }
  let url: string
  if (clip.song) {
    url = await getSongPlayUrl(clip.song)
  } else if (clip.stem_file) {
    url = await getStemDownloadUrl(clip.stem_file)
  } else if (clip.is_external && mixId) {
    url = await getMixClipPlayUrl(mixId, clip.id)
  } else {
    throw new Error('El clip no tiene una fuente de audio válida.')
  }
  urlCache.set(clip.id, url)
  return url
}

export function preloadClipUrls(
  clips: MixClip[],
  mixId: string | undefined,
  urlCache: Map<string, string>,
  onError: (message: string) => void
) {
  clips.forEach((clip) => {
    if (urlCache.has(clip.id)) {
      return
    }
    void fetchClipAudioUrl(clip, mixId, urlCache).catch((error: unknown) => {
      if (clip.song || clip.stem_file || (clip.is_external && mixId)) {
        onError(error instanceof Error ? error.message : 'No se pudo obtener el audio.')
      }
    })
  })
}

export function getOrCreateClipAudio(
  clipId: string,
  audioMap: Map<string, HTMLAudioElement>,
  gainMap: Map<string, GainNode>,
  contextRef: React.MutableRefObject<AudioContext | null>,
  onError: (msg: string) => void
): HTMLAudioElement {
  const existing = audioMap.get(clipId)
  if (existing) {
    return existing
  }
  const audio = new Audio()
  audio.preload = 'auto'
  audio.crossOrigin = 'anonymous'
  audio.onerror = () => onError('No se pudo cargar la pista de audio.')
  audioMap.set(clipId, audio)
  if (window.AudioContext) {
    const ctx = contextRef.current ?? new window.AudioContext()
    contextRef.current = ctx
    const src = ctx.createMediaElementSource(audio)
    const gain = ctx.createGain()
    src.connect(gain)
    gain.connect(ctx.destination)
    gainMap.set(clipId, gain)
  }
  return audio
}
