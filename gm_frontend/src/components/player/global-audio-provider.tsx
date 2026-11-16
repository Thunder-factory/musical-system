import { useCallback, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { GlobalAudioContext } from './global-audio-context'
import type { GlobalAudioTrack } from './global-audio-context'

export default function GlobalAudioProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [track, setTrack] = useState<GlobalAudioTrack | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  const playTrack = useCallback(
    (nextTrack: GlobalAudioTrack) => {
      if (track?.id === nextTrack.id && audioRef.current) {
        void audioRef.current.play().catch(() => {})
        return
      }

      setTrack(nextTrack)
      setCurrentTime(0)
      setDuration(0)
    },
    [track?.id]
  )

  const pause = useCallback(() => {
    audioRef.current?.pause()
  }, [])

  const updateTrack = useCallback((patch: Partial<GlobalAudioTrack>) => {
    setTrack((current) => {
      if (!current) {
        return current
      }
      const nextTrack = { ...current, ...patch }
      return nextTrack
    })
  }, [])

  const seek = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time
    }
    setCurrentTime(time)
  }, [])

  const close = useCallback(() => {
    track?.onClose?.()
    audioRef.current?.pause()
    setTrack(null)
    setIsPlaying(false)
    setCurrentTime(0)
    setDuration(0)
  }, [track])

  const value = useMemo(
    () => ({
      audioRef,
      track,
      isPlaying,
      currentTime,
      duration,
      playTrack,
      updateTrack,
      pause,
      seek,
      close,
      setPlaying: setIsPlaying,
      setCurrentTime,
      setDuration,
    }),
    [track, isPlaying, currentTime, duration, playTrack, updateTrack, pause, seek, close]
  )

  return <GlobalAudioContext.Provider value={value}>{children}</GlobalAudioContext.Provider>
}
