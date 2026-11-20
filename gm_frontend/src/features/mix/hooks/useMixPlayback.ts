import { useEffect, useRef, useState } from 'react'

import type { MixClip } from '../api/mix.api'
import {
  preloadClipUrls,
  recordsEqual,
  type PlaybackMode,
  type PlaybackState,
} from './mix-playback-audio'
import {
  pausePlaybackEngine,
  scheduleClipPlayback,
  stopPlaybackEngine,
} from './mix-playback-controls'
import {
  disposePlaybackResources,
  getCurrentTimelinePosition,
  syncPlaybackFrame,
  type PlaybackEngineState,
} from './mix-playback-engine'

export type { PlaybackMode, PlaybackState }

export default function useMixPlayback(clips: MixClip[], mixId?: string) {
  const [playbackState, setPlaybackState] = useState<PlaybackState>('idle')
  const [playbackMode, setPlaybackMode] = useState<PlaybackMode | null>(null)
  const [playingClipId, setPlayingClipId] = useState<string | null>(null)
  const [timelinePositionMs, setTimelinePositionMs] = useState(0)
  const [mutedClipIds, setMutedClipIds] = useState<Record<string, boolean>>({})
  const [soloClipIds, setSoloClipIds] = useState<Record<string, boolean>>({})
  const [playbackError, setPlaybackError] = useState<string | null>(null)

  const audioRef = useRef(new Map<string, HTMLAudioElement>())
  const audioContextRef = useRef<AudioContext | null>(null)
  const gainNodeRef = useRef(new Map<string, GainNode>())
  const urlCacheRef = useRef(new Map<string, string>())
  const timersRef = useRef<number[]>([])
  const rafRef = useRef<number | null>(null)
  const genRef = useRef(0)
  const startedAtRef = useRef(0)
  const posRef = useRef(0)
  const stateRef = useRef<PlaybackState>('idle')
  const modeRef = useRef<PlaybackMode | null>(null)
  const targetClipRef = useRef<string | null>(null)
  const clipsRef = useRef(clips)
  const totalDurationRef = useRef(0)
  const mutedRef = useRef(mutedClipIds)
  const soloRef = useRef(soloClipIds)
  const removedRef = useRef(new Set<string>())

  const totalDurationMs = Math.max(
    0,
    ...clips.map((c) => c.timeline_start_ms + Math.max(c.duration_ms, 0))
  )

  const getEngine = (): PlaybackEngineState => ({
    audioRef,
    audioContextRef,
    gainNodeRef,
    urlCacheRef,
    timersRef,
    rafRef,
    genRef,
    posRef,
    startedAtRef,
    stateRef,
    modeRef,
    targetClipRef,
    clipsRef,
    totalDurationRef,
    mutedRef,
    soloRef,
    removedRef,
  })

  const callbacks = {
    setTimelinePositionMs,
    setPlaybackMode,
    setPlayingClipId,
    setPlaybackState,
    setPlaybackError,
  }

  useEffect(() => {
    clipsRef.current = clips
    mutedRef.current = mutedClipIds
    soloRef.current = soloClipIds
    totalDurationRef.current = totalDurationMs
  }, [clips, mutedClipIds, soloClipIds, totalDurationMs])

  useEffect(() => {
    const nextMuted: Record<string, boolean> = {}
    const nextSolo: Record<string, boolean> = {}
    clips.forEach((c) => {
      if (c.is_muted) {
        nextMuted[c.id] = true
      }
      if (c.is_solo) {
        nextSolo[c.id] = true
      }
    })
    setMutedClipIds((cur) => (recordsEqual(cur, nextMuted) ? cur : nextMuted))
    setSoloClipIds((cur) => (recordsEqual(cur, nextSolo) ? cur : nextSolo))
  }, [clips])

  useEffect(() => {
    preloadClipUrls(clips, mixId, urlCacheRef.current, setPlaybackError)
  }, [clips, mixId])

  useEffect(() => {
    return () => disposePlaybackResources(genRef, timersRef, rafRef, audioRef, audioContextRef)
  }, [])

  function tick() {
    if (stateRef.current !== 'playing') {
      return
    }
    const { positionMs, ended } = syncPlaybackFrame(getEngine())
    setTimelinePositionMs(positionMs)
    if (ended) {
      stopPlaybackEngine(getEngine(), callbacks)
      return
    }
    rafRef.current = requestAnimationFrame(tick)
  }

  const startPlayback = (mode: PlaybackMode, startPosMs: number, clipId: string | null = null) =>
    scheduleClipPlayback(getEngine(), mode, startPosMs, clipId, mixId, callbacks, tick)

  return {
    playbackState,
    playbackMode,
    playingClipId,
    timelinePositionMs,
    totalDurationMs,
    mutedClipIds,
    soloClipIds,
    playbackError,
    toggleGlobalPlayback: () => {
      if (stateRef.current === 'playing') {
        if (modeRef.current === 'global') {
          pausePlaybackEngine(getEngine(), callbacks)
        } else {
          startPlayback('global', 0)
        }
      } else if (stateRef.current === 'paused' && modeRef.current) {
        startPlayback(
          'global',
          modeRef.current === 'global' ? posRef.current : getCurrentTimelinePosition(getEngine())
        )
      } else {
        startPlayback('global', getCurrentTimelinePosition(getEngine()))
      }
    },
    restartGlobalPlayback: () => startPlayback('global', 0),
    toggleClipPlayback: (clipId: string) => {
      if (!clipsRef.current.some((c) => c.id === clipId)) {
        return
      }
      if (modeRef.current === 'individual' && targetClipRef.current === clipId) {
        if (stateRef.current === 'playing') {
          pausePlaybackEngine(getEngine(), callbacks)
          return
        }
        if (stateRef.current === 'paused') {
          startPlayback('individual', posRef.current, clipId)
          return
        }
      }
      startPlayback('individual', 0, clipId)
    },
    stopPlayback: () => stopPlaybackEngine(getEngine(), callbacks),
    removeClipFromPlayback: (clipId: string) => {
      removedRef.current.add(clipId)
      audioRef.current.get(clipId)?.pause()
      audioRef.current.delete(clipId)
      gainNodeRef.current.delete(clipId)
      if (targetClipRef.current === clipId) {
        stopPlaybackEngine(getEngine(), callbacks)
      }
    },
    setTimelinePosition: (positionMs: number) => {
      const bounded = Math.max(0, Math.min(positionMs, totalDurationMs))
      posRef.current = bounded
      setTimelinePositionMs(bounded)
      if (stateRef.current === 'playing' && modeRef.current) {
        const target =
          modeRef.current === 'individual' && targetClipRef.current
            ? clipsRef.current.find((c) => c.id === targetClipRef.current)
            : null
        startPlayback(
          modeRef.current,
          target ? Math.max(0, bounded - target.timeline_start_ms) : bounded,
          targetClipRef.current
        )
      }
    },
    toggleMute: (clipId: string) =>
      setMutedClipIds((cur) => ({ ...cur, [clipId]: !cur[clipId] })),
    toggleSolo: (clipId: string) =>
      setSoloClipIds((cur) => ({ ...cur, [clipId]: !cur[clipId] })),
  }
}
