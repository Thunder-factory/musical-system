import type { MixClip } from '../api/mix.api'
import { type PlaybackMode, type PlaybackState } from './mix-playback-audio'
import {
  activateClipAudio,
  clearPlaybackTimers,
  getCurrentTimelinePosition,
  type PlaybackEngineState,
} from './mix-playback-engine'

export interface PlaybackStateCallbacks {
  setTimelinePositionMs: (ms: number) => void
  setPlaybackMode: (mode: PlaybackMode | null) => void
  setPlayingClipId: (clipId: string | null) => void
  setPlaybackState: (state: PlaybackState) => void
  setPlaybackError: (msg: string | null) => void
}

export function stopPlaybackEngine(
  engine: PlaybackEngineState,
  callbacks: PlaybackStateCallbacks
) {
  engine.genRef.current += 1
  clearPlaybackTimers(engine.timersRef)
  engine.audioRef.current.forEach((audio) => {
    audio.pause()
    audio.removeAttribute('src')
    audio.load()
  })
  engine.audioRef.current.clear()
  engine.gainNodeRef.current.clear()
  if (engine.rafRef.current !== null) {
    cancelAnimationFrame(engine.rafRef.current)
  }
  engine.posRef.current = 0
  engine.modeRef.current = null
  engine.targetClipRef.current = null
  engine.stateRef.current = 'idle'
  callbacks.setTimelinePositionMs(0)
  callbacks.setPlaybackMode(null)
  callbacks.setPlayingClipId(null)
  callbacks.setPlaybackState('idle')
}

export function pausePlaybackEngine(
  engine: PlaybackEngineState,
  callbacks: Pick<PlaybackStateCallbacks, 'setPlaybackState'>
) {
  const cur = getCurrentTimelinePosition(engine)
  if (engine.modeRef.current === 'individual' && engine.targetClipRef.current) {
    const clip = engine.clipsRef.current.find((c) => c.id === engine.targetClipRef.current)
    engine.posRef.current = Math.max(0, cur - (clip?.timeline_start_ms ?? 0))
  } else {
    engine.posRef.current = cur
  }
  clearPlaybackTimers(engine.timersRef)
  engine.audioRef.current.forEach((audio) => audio.pause())
  if (engine.rafRef.current !== null) {
    cancelAnimationFrame(engine.rafRef.current)
  }
  engine.stateRef.current = 'paused'
  callbacks.setPlaybackState('paused')
}

export function scheduleClipPlayback(
  engine: PlaybackEngineState,
  mode: PlaybackMode,
  startPosMs: number,
  clipId: string | null,
  mixId: string | undefined,
  callbacks: PlaybackStateCallbacks,
  onTick: () => void
) {
  callbacks.setPlaybackError(null)
  engine.removedRef.current.clear()
  engine.genRef.current += 1
  const gen = engine.genRef.current
  clearPlaybackTimers(engine.timersRef)
  engine.audioRef.current.forEach((audio) => audio.pause())

  const target: MixClip | undefined = clipId
    ? engine.clipsRef.current.find((c) => c.id === clipId)
    : undefined
  const localPos = Math.max(0, startPosMs)
  const bounded = mode === 'individual' && target ? target.timeline_start_ms + localPos : localPos
  engine.posRef.current = localPos
  engine.startedAtRef.current = performance.now()
  engine.modeRef.current = mode
  engine.targetClipRef.current = clipId
  engine.stateRef.current = 'playing'
  callbacks.setPlaybackMode(mode)
  callbacks.setPlayingClipId(clipId)
  callbacks.setPlaybackState('playing')

  engine.clipsRef.current
    .filter(
      (c) =>
        (mode !== 'individual' || c.id === clipId) &&
        bounded < c.timeline_start_ms + c.duration_ms
    )
    .forEach((c) => {
      const delay = mode === 'individual' ? 0 : Math.max(0, c.timeline_start_ms - bounded)
      if (delay === 0) {
        void activateClipAudio(c, gen, bounded, mixId, engine, callbacks.setPlaybackError)
      } else {
        engine.timersRef.current.push(
          window.setTimeout(
            () =>
              void activateClipAudio(
                c,
                gen,
                getCurrentTimelinePosition(engine),
                mixId,
                engine,
                callbacks.setPlaybackError
              ),
            delay
          )
        )
      }
    })
  engine.rafRef.current = requestAnimationFrame(onTick)
}
