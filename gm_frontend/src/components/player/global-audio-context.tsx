import { createContext } from 'react'
import type { RefObject } from 'react'

export interface GlobalAudioTrack {
  id: string
  audioUrl: string
  title: string
  subtitle?: string
  coverUrl?: string | null
  showLyrics?: boolean
  onToggleLyrics?: () => void
  onEnded?: () => void
  onClose?: () => void
}

export interface GlobalAudioContextValue {
  audioRef: RefObject<HTMLAudioElement | null>
  track: GlobalAudioTrack | null
  isPlaying: boolean
  currentTime: number
  duration: number
  playTrack: (nextTrack: GlobalAudioTrack) => void
  updateTrack: (patch: Partial<GlobalAudioTrack>) => void
  pause: () => void
  seek: (time: number) => void
  close: () => void
  setPlaying: (playing: boolean) => void
  setCurrentTime: (time: number) => void
  setDuration: (duration: number) => void
}

export const GlobalAudioContext = createContext<GlobalAudioContextValue | null>(null)
