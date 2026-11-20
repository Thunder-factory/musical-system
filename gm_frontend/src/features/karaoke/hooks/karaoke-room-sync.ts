import type { KaraokeParticipant, KaraokeRoom, LyricTimestamp } from '../../../types'

export interface RawRoom extends Omit<KaraokeRoom, 'participants' | 'lyricsTimestamps'> {
  participants?: Record<string, KaraokeParticipant>
  lyricsTimestamps?: LyricTimestamp[] | Record<string, LyricTimestamp>
  volumes?: Record<string, number>
}

export function normalizeRoom(raw: RawRoom): KaraokeRoom {
  return {
    ...raw,
    participants: Object.values(raw.participants ?? {}),
    lyricsTimestamps: Array.isArray(raw.lyricsTimestamps)
      ? raw.lyricsTimestamps
      : Object.values(raw.lyricsTimestamps ?? {}),
    volumes: raw.volumes,
  }
}

export function syncGuestAudio(raw: RawRoom, userId: string, audio: HTMLAudioElement | null) {
  if (raw.hostId === userId || !audio) {
    return
  }
  if (raw.state === 'playing') {
    if (Math.abs(audio.currentTime - raw.currentTime) > 0.5) {
      audio.currentTime = raw.currentTime
    }
    if (audio.paused) {
      audio.play().catch(() => {})
    }
  } else if (raw.state === 'ended' && !audio.paused) {
    audio.pause()
  } else if (raw.state === 'paused') {
    if (!audio.paused) {
      audio.pause()
    }
    audio.currentTime = raw.currentTime
  }
}

export function getResponseStatus(err: unknown): number | undefined {
  return typeof err === 'object' && err !== null && 'response' in err
    ? (err as { response?: { status?: number } }).response?.status
    : undefined
}
