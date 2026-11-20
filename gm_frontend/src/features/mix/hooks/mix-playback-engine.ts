import type { MutableRefObject } from 'react'

import type { MixClip } from '../api/mix.api'
import {
  applyClipVolume,
  fetchClipAudioUrl,
  getOrCreateClipAudio,
  type PlaybackMode,
  type PlaybackState,
} from './mix-playback-audio'

export interface PlaybackEngineState {
  audioRef: MutableRefObject<Map<string, HTMLAudioElement>>
  audioContextRef: MutableRefObject<AudioContext | null>
  gainNodeRef: MutableRefObject<Map<string, GainNode>>
  urlCacheRef: MutableRefObject<Map<string, string>>
  timersRef: MutableRefObject<number[]>
  rafRef: MutableRefObject<number | null>
  genRef: MutableRefObject<number>
  posRef: MutableRefObject<number>
  startedAtRef: MutableRefObject<number>
  stateRef: MutableRefObject<PlaybackState>
  modeRef: MutableRefObject<PlaybackMode | null>
  targetClipRef: MutableRefObject<string | null>
  clipsRef: MutableRefObject<MixClip[]>
  totalDurationRef: MutableRefObject<number>
  mutedRef: MutableRefObject<Record<string, boolean>>
  soloRef: MutableRefObject<Record<string, boolean>>
  removedRef: MutableRefObject<Set<string>>
}

export function clearPlaybackTimers(timersRef: MutableRefObject<number[]>) {
  timersRef.current.forEach((timerId) => window.clearTimeout(timerId))
  timersRef.current = []
}

export function getCurrentTimelinePosition(engine: PlaybackEngineState): number {
  const elapsed =
    engine.stateRef.current === 'playing'
      ? engine.posRef.current + (performance.now() - engine.startedAtRef.current)
      : engine.posRef.current
  if (engine.modeRef.current === 'individual' && engine.targetClipRef.current) {
    const clip = engine.clipsRef.current.find((c) => c.id === engine.targetClipRef.current)
    return (clip?.timeline_start_ms ?? 0) + elapsed
  }
  return elapsed
}

export async function activateClipAudio(
  clip: MixClip,
  generation: number,
  positionMs: number,
  mixId: string | undefined,
  engine: PlaybackEngineState,
  onError: (message: string) => void
) {
  if (
    engine.removedRef.current.has(clip.id) ||
    generation !== engine.genRef.current ||
    engine.stateRef.current !== 'playing'
  ) {
    return
  }
  let url: string
  try {
    url = await fetchClipAudioUrl(clip, mixId, engine.urlCacheRef.current)
  } catch (err) {
    onError(err instanceof Error ? err.message : 'No se pudo obtener el audio.')
    return
  }
  if (!url || generation !== engine.genRef.current || engine.stateRef.current !== 'playing') {
    return
  }

  const audio = getOrCreateClipAudio(
    clip.id,
    engine.audioRef.current,
    engine.gainNodeRef.current,
    engine.audioContextRef,
    onError
  )
  audio.defaultPlaybackRate = 1
  audio.playbackRate = 1
  if (audio.src !== url) {
    audio.src = url
  }
  audio.currentTime =
    clip.start_time_ms / 1000 + Math.max(0, positionMs - clip.timeline_start_ms) / 1000
  applyClipVolume(
    clip,
    audio,
    engine.gainNodeRef.current.get(clip.id),
    positionMs,
    engine.modeRef.current ?? 'global',
    engine.mutedRef.current,
    engine.soloRef.current
  )
  try {
    const playPromise = audio.play()
    await engine.audioContextRef.current?.resume()
    await playPromise
  } catch (err) {
    onError(
      err instanceof DOMException && err.name === 'NotAllowedError'
        ? 'El navegador bloqueó la reproducción. Presiona reproducir nuevamente.'
        : 'No se pudo reproducir el clip.'
    )
  }
}

export function syncPlaybackFrame(engine: PlaybackEngineState): {
  positionMs: number
  ended: boolean
} {
  const positionMs = getCurrentTimelinePosition(engine)
  engine.clipsRef.current.forEach((clip) => {
    const audio = engine.audioRef.current.get(clip.id)
    if (!audio) {
      return
    }
    const inside =
      positionMs >= clip.timeline_start_ms && positionMs < clip.timeline_start_ms + clip.duration_ms
    if (!inside) {
      audio.pause()
      return
    }
    applyClipVolume(
      clip,
      audio,
      engine.gainNodeRef.current.get(clip.id),
      positionMs,
      engine.modeRef.current ?? 'global',
      engine.mutedRef.current,
      engine.soloRef.current
    )
  })
  const target = engine.clipsRef.current.find((c) => c.id === engine.targetClipRef.current)
  const ended =
    engine.modeRef.current === 'individual' && target
      ? positionMs >= target.timeline_start_ms + target.duration_ms
      : positionMs >= engine.totalDurationRef.current
  return { positionMs, ended }
}

export function disposePlaybackResources(
  genRef: MutableRefObject<number>,
  timersRef: MutableRefObject<number[]>,
  rafRef: MutableRefObject<number | null>,
  audioRef: MutableRefObject<Map<string, HTMLAudioElement>>,
  audioContextRef: MutableRefObject<AudioContext | null>
) {
  genRef.current += 1
  clearPlaybackTimers(timersRef)
  audioRef.current.forEach((audio) => audio.pause())
  if (rafRef.current !== null) {
    cancelAnimationFrame(rafRef.current)
  }
  void audioContextRef.current?.close()
}
