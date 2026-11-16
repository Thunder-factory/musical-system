import { useEffect, useRef, useState } from 'react'
import { getMixClipPlayUrl } from '../api/modules/mix.api'
import type { MixClip } from '../api/modules/mix.api'
import { getStemDownloadUrl } from '../api/modules/stems.api'
import { getSongPlayUrl } from '../api/modules/songs.api'

export type PlaybackMode = 'global' | 'individual'
export type PlaybackState = 'idle' | 'playing' | 'paused'

interface UseMixPlaybackResult {
  playbackState: PlaybackState
  playbackMode: PlaybackMode | null
  playingClipId: string | null
  timelinePositionMs: number
  totalDurationMs: number
  mutedClipIds: Record<string, boolean>
  soloClipIds: Record<string, boolean>
  playbackError: string | null
  toggleGlobalPlayback: () => void
  restartGlobalPlayback: () => void
  toggleClipPlayback: (clipId: string) => void
  stopPlayback: () => void
  removeClipFromPlayback: (clipId: string) => void
  setTimelinePosition: (positionMs: number) => void
  toggleMute: (clipId: string) => void
  toggleSolo: (clipId: string) => void
}

function clampVolume(volume: number) {
  return Math.max(0, Math.min(volume, 2))
}

function nowMs() {
  return performance.now()
}

function recordsEqual(first: Record<string, boolean>, second: Record<string, boolean>): boolean {
  const firstKeys = Object.keys(first).filter((key) => first[key])
  const secondKeys = Object.keys(second).filter((key) => second[key])
  return firstKeys.length === secondKeys.length && firstKeys.every((key) => second[key] === true)
}

export default function useMixPlayback(clips: MixClip[], mixId?: string): UseMixPlaybackResult {
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
  const generationRef = useRef(0)
  const startedAtRef = useRef(0)
  const positionRef = useRef(0)
  const playbackStateRef = useRef<PlaybackState>('idle')
  const playbackModeRef = useRef<PlaybackMode | null>(null)
  const targetClipRef = useRef<string | null>(null)
  const clipsRef = useRef(clips)
  const totalDurationRef = useRef(0)
  const mutedRef = useRef(mutedClipIds)
  const soloRef = useRef(soloClipIds)
  const removedClipIdsRef = useRef(new Set<string>())

  const totalDurationMs = Math.max(
    0,
    ...clips.map((clip) => clip.timeline_start_ms + Math.max(clip.duration_ms, 0))
  )
  useEffect(() => {
    clipsRef.current = clips
    mutedRef.current = mutedClipIds
    soloRef.current = soloClipIds
    totalDurationRef.current = totalDurationMs
  }, [clips, mutedClipIds, soloClipIds, totalDurationMs])

  useEffect(() => {
    const nextMuted: Record<string, boolean> = {}
    const nextSolo: Record<string, boolean> = {}
    clips.forEach((clip) => {
      if (clip.is_muted) {
        nextMuted[clip.id] = true
      }
      if (clip.is_solo) {
        nextSolo[clip.id] = true
      }
    })
    setMutedClipIds((current) => (recordsEqual(current, nextMuted) ? current : nextMuted))
    setSoloClipIds((current) => (recordsEqual(current, nextSolo) ? current : nextSolo))
  }, [clips])

  function setState(next: PlaybackState) {
    playbackStateRef.current = next
    setPlaybackState(next)
  }

  function clearTimers() {
    timersRef.current.forEach((timer) => window.clearTimeout(timer))
    timersRef.current = []
  }

  function pauseAllAudio() {
    audioRef.current.forEach((audio) => audio.pause())
  }

  function currentPosition() {
    const elapsedPosition =
      playbackStateRef.current === 'playing'
        ? positionRef.current + (performance.now() - startedAtRef.current)
        : positionRef.current

    if (playbackModeRef.current === 'individual' && targetClipRef.current) {
      const clip = clipsRef.current.find((item) => item.id === targetClipRef.current)
      return (clip?.timeline_start_ms ?? 0) + elapsedPosition
    }
    return elapsedPosition
  }

  function isAudible(clip: MixClip, mode: PlaybackMode) {
    if (mutedRef.current[clip.id]) {
      return false
    }
    if (mode === 'individual') {
      return true
    }
    const soloIds = Object.keys(soloRef.current).filter((id) => soloRef.current[id])
    return soloIds.length === 0 || Boolean(soloRef.current[clip.id])
  }

  function applyVolume(clip: MixClip, audio: HTMLAudioElement, positionMs: number) {
    if (!isAudible(clip, playbackModeRef.current ?? 'global')) {
      const gain = gainNodeRef.current.get(clip.id)
      if (gain) {
        gain.gain.value = 0
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
    const gain = gainNodeRef.current.get(clip.id)
    if (gain) {
      gain.gain.value = targetGain
      audio.volume = 1
    } else {
      // Fallback for browsers that do not expose Web Audio. HTMLMediaElement
      // cannot represent gain above 1, so this still preserves attenuation.
      audio.volume = Math.min(targetGain, 1)
    }
  }

  async function getClipUrl(clip: MixClip) {
    const cached = urlCacheRef.current.get(clip.id)
    if (cached) {
      return cached
    }
    if (clip.song) {
      const url = await getSongPlayUrl(clip.song)
      urlCacheRef.current.set(clip.id, url)
      return url
    }
    if (clip.stem_file) {
      const url = await getStemDownloadUrl(clip.stem_file)
      urlCacheRef.current.set(clip.id, url)
      return url
    }
    if (clip.is_external && mixId) {
      const url = await getMixClipPlayUrl(mixId, clip.id)
      urlCacheRef.current.set(clip.id, url)
      return url
    }
    throw new Error('El clip no tiene una fuente de audio válida.')
  }

  useEffect(() => {
    clips.forEach((clip) => {
      if (urlCacheRef.current.has(clip.id)) {
        return
      }
      const request = clip.song
        ? getSongPlayUrl(clip.song)
        : clip.stem_file
          ? getStemDownloadUrl(clip.stem_file)
          : clip.is_external && mixId
            ? getMixClipPlayUrl(mixId, clip.id)
            : Promise.resolve(null)
      void request
        .then((url) => {
          if (url) {
            urlCacheRef.current.set(clip.id, url)
          }
        })
        .catch((error: unknown) => {
          const message = error instanceof Error ? error.message : 'No se pudo obtener el audio.'
          console.error(`No se pudo obtener el audio del clip ${clip.id}:`, error)
          setPlaybackError(message)
        })
    })
  }, [clips, mixId])

  async function activateClip(clip: MixClip, generation: number, positionMs: number) {
    if (
      removedClipIdsRef.current.has(clip.id) ||
      generation !== generationRef.current ||
      playbackStateRef.current !== 'playing'
    ) {
      return
    }
    const cachedUrl = urlCacheRef.current.get(clip.id)
    let url: string
    try {
      url = cachedUrl ?? (await getClipUrl(clip))
    } catch (error) {
      const message = error instanceof Error ? error.message : 'No se pudo obtener el audio.'
      console.error(`No se pudo preparar el audio del clip ${clip.id}:`, error)
      setPlaybackError(message)
      return
    }
    if (!url || generation !== generationRef.current || playbackStateRef.current !== 'playing') {
      return
    }

    let audio = audioRef.current.get(clip.id)
    if (!audio) {
      audio = new Audio()
      audio.preload = 'auto'
      audio.crossOrigin = 'anonymous'
      audio.onerror = () => {
        const mediaError = audio?.error
        const message = mediaError
          ? `Error de audio (${mediaError.code}): no se pudo cargar la pista.`
          : 'No se pudo cargar la pista de audio.'
        console.error(`Error cargando el audio del clip ${clip.id}:`, mediaError)
        setPlaybackError(message)
      }
      audioRef.current.set(clip.id, audio)
      const AudioContextClass = window.AudioContext
      if (AudioContextClass) {
        const context = audioContextRef.current ?? new AudioContextClass()
        audioContextRef.current = context
        const source = context.createMediaElementSource(audio)
        const gain = context.createGain()
        source.connect(gain)
        gain.connect(context.destination)
        gainNodeRef.current.set(clip.id, gain)
      }
    }
    // Cada clip debe reproducirse a velocidad normal. Esto evita conservar
    // una velocidad alterada si el elemento de audio fue reutilizado.
    audio.defaultPlaybackRate = 1
    audio.playbackRate = 1
    if (audio.src !== url) {
      audio.src = url
    }
    audio.currentTime =
      clip.start_time_ms / 1000 + Math.max(0, positionMs - clip.timeline_start_ms) / 1000
    applyVolume(clip, audio, positionMs)
    try {
      // Invocar play() antes de esperar a AudioContext conserva mejor el gesto
      // del usuario cuando la URL ya fue precargada.
      const playPromise = audio.play()
      await audioContextRef.current?.resume()
      await playPromise
    } catch (error) {
      const message =
        error instanceof DOMException && error.name === 'NotAllowedError'
          ? 'El navegador bloqueó la reproducción. Presiona reproducir nuevamente.'
          : error instanceof Error
            ? error.message
            : 'No se pudo reproducir el clip.'
      setPlaybackError(message)
      console.error('No se pudo reproducir el clip:', error)
    }
  }

  function tick() {
    if (playbackStateRef.current !== 'playing') {
      return
    }
    const positionMs = currentPosition()
    setTimelinePositionMs(positionMs)

    clipsRef.current.forEach((clip) => {
      const audio = audioRef.current.get(clip.id)
      if (audio) {
        const clipStart = clip.timeline_start_ms
        const clipEnd = clipStart + clip.duration_ms
        const isInsideClip = positionMs >= clipStart && positionMs < clipEnd
        if (!isInsideClip) {
          audio.pause()
        } else {
          applyVolume(clip, audio, positionMs)
        }
      }
    })

    const endPosition =
      playbackModeRef.current === 'individual'
        ? (clipsRef.current.find((clip) => clip.id === targetClipRef.current)?.timeline_start_ms ??
          0)
        : totalDurationRef.current
    const targetClip = clipsRef.current.find((clip) => clip.id === targetClipRef.current)
    const reachedEnd =
      playbackModeRef.current === 'individual' && targetClip
        ? positionMs >= targetClip.timeline_start_ms + targetClip.duration_ms
        : positionMs >= endPosition

    if (reachedEnd) {
      stopPlayback()
      return
    }
    rafRef.current = requestAnimationFrame(tick)
  }

  function startPlayback(
    mode: PlaybackMode,
    startPositionMs: number,
    clipId: string | null = null
  ) {
    setPlaybackError(null)
    removedClipIdsRef.current.clear()
    generationRef.current += 1
    const generation = generationRef.current
    clearTimers()
    pauseAllAudio()
    const targetClip = clipId ? clipsRef.current.find((clip) => clip.id === clipId) : null
    const localPosition = Math.max(0, startPositionMs)
    const boundedPosition =
      mode === 'individual' && targetClip
        ? targetClip.timeline_start_ms + localPosition
        : localPosition
    positionRef.current = localPosition
    // positionRef ya representa la posición inicial. El reloj solo debe
    // guardar el instante de inicio; restar localPosition aquí hacía que
    // currentPosition la sumara dos veces al reanudar o buscar.
    startedAtRef.current = nowMs()
    playbackModeRef.current = mode
    targetClipRef.current = clipId
    setPlaybackMode(mode)
    setPlayingClipId(clipId)
    setState('playing')

    const candidates = clipsRef.current.filter((clip) => {
      const clipEnd = clip.timeline_start_ms + clip.duration_ms
      const inRange =
        mode === 'individual'
          ? clip.id === clipId && boundedPosition < clipEnd
          : boundedPosition < clipEnd
      return inRange
    })

    candidates.forEach((clip) => {
      const delay =
        mode === 'individual' ? 0 : Math.max(0, clip.timeline_start_ms - boundedPosition)
      if (delay === 0) {
        void activateClip(clip, generation, boundedPosition)
      } else {
        const timer = window.setTimeout(() => {
          void activateClip(clip, generation, currentPosition())
        }, delay)
        timersRef.current.push(timer)
      }
    })
    rafRef.current = requestAnimationFrame(tick)
  }

  function pausePlayback() {
    const current = currentPosition()
    if (playbackModeRef.current === 'individual' && targetClipRef.current) {
      const clip = clipsRef.current.find((item) => item.id === targetClipRef.current)
      positionRef.current = Math.max(0, current - (clip?.timeline_start_ms ?? 0))
    } else {
      positionRef.current = current
    }
    clearTimers()
    pauseAllAudio()
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current)
    }
    setState('paused')
  }

  function stopPlayback() {
    generationRef.current += 1
    clearTimers()
    audioRef.current.forEach((audio) => {
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
    })
    // Stop debe crear una reproducción completamente nueva. Conservamos
    // únicamente las URLs firmadas para evitar consultas innecesarias.
    audioRef.current.clear()
    gainNodeRef.current.clear()
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current)
    }
    positionRef.current = 0
    setTimelinePositionMs(0)
    setPlaybackMode(null)
    setPlayingClipId(null)
    playbackModeRef.current = null
    targetClipRef.current = null
    setState('idle')
  }

  function removeClipFromPlayback(clipId: string) {
    removedClipIdsRef.current.add(clipId)
    const audio = audioRef.current.get(clipId)
    audio?.pause()
    audioRef.current.delete(clipId)
    gainNodeRef.current.delete(clipId)
    if (targetClipRef.current === clipId) {
      stopPlayback()
    }
  }

  function resumePlayback() {
    const mode = playbackModeRef.current
    if (!mode) {
      return
    }
    startPlayback(mode, positionRef.current, targetClipRef.current)
  }

  function toggleGlobalPlayback() {
    if (playbackStateRef.current === 'playing') {
      if (playbackModeRef.current === 'global') {
        pausePlayback()
      } else {
        startPlayback('global', 0)
      }
      return
    }
    if (playbackStateRef.current === 'paused' && playbackModeRef.current) {
      if (playbackModeRef.current === 'global') {
        resumePlayback()
      } else {
        startPlayback('global', currentPosition())
      }
      return
    }
    startPlayback('global', currentPosition())
  }

  function restartGlobalPlayback() {
    startPlayback('global', 0)
  }

  function toggleClipPlayback(clipId: string) {
    const clip = clipsRef.current.find((item) => item.id === clipId)
    if (!clip) {
      return
    }
    if (
      playbackStateRef.current === 'playing' &&
      playbackModeRef.current === 'individual' &&
      targetClipRef.current === clipId
    ) {
      pausePlayback()
      return
    }
    if (
      playbackStateRef.current === 'paused' &&
      playbackModeRef.current === 'individual' &&
      targetClipRef.current === clipId
    ) {
      resumePlayback()
      return
    }
    startPlayback('individual', 0, clipId)
  }

  function setTimelinePosition(positionMs: number) {
    const boundedPosition = Math.max(0, Math.min(positionMs, totalDurationMs))
    positionRef.current = boundedPosition
    setTimelinePositionMs(boundedPosition)
    if (playbackStateRef.current === 'playing' && playbackModeRef.current) {
      const targetClip =
        playbackModeRef.current === 'individual' && targetClipRef.current
          ? clipsRef.current.find((clip) => clip.id === targetClipRef.current)
          : null
      const playbackPosition = targetClip
        ? Math.max(0, boundedPosition - targetClip.timeline_start_ms)
        : boundedPosition
      startPlayback(playbackModeRef.current, playbackPosition, targetClipRef.current)
    }
  }

  function toggleMute(clipId: string) {
    setMutedClipIds((current) => ({ ...current, [clipId]: !current[clipId] }))
  }

  function toggleSolo(clipId: string) {
    setSoloClipIds((current) => ({ ...current, [clipId]: !current[clipId] }))
  }

  useEffect(() => {
    return () => {
      generationRef.current += 1
      clearTimers()
      pauseAllAudio()
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
      void audioContextRef.current?.close()
    }
  }, [])

  return {
    playbackState,
    playbackMode,
    playingClipId,
    timelinePositionMs,
    totalDurationMs,
    mutedClipIds,
    soloClipIds,
    playbackError,
    toggleGlobalPlayback,
    restartGlobalPlayback,
    toggleClipPlayback,
    stopPlayback,
    removeClipFromPlayback,
    setTimelinePosition,
    toggleMute,
    toggleSolo,
  }
}
