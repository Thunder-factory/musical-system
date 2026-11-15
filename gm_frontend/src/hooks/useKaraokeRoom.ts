import { useCallback, useEffect, useRef, useState } from 'react'
import { onValue, ref, update } from 'firebase/database'

import { joinKaraokeRoom } from '../api/modules/karaoke.api'

// @ts-expect-error — firebase.js es JS puro; Vite resuelve el módulo correctamente
import { db } from '../firebase.js'

import type { KaraokeParticipant, KaraokeRoom, LyricTimestamp } from '../types'

interface RawRoom extends Omit<KaraokeRoom, 'participants' | 'lyricsTimestamps'> {
  participants?: Record<string, KaraokeParticipant>
  lyricsTimestamps?: LyricTimestamp[] | Record<string, LyricTimestamp>
  volumes?: Record<string, number>
}

interface Params {
  roomCode: string
  userId: string
  audioRef: React.RefObject<HTMLAudioElement | null>
}

export function useKaraokeRoom({ roomCode, userId, audioRef }: Params) {
  const [room, setRoom] = useState<KaraokeRoom | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'not_found' | 'error'>('loading')
  const syncRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const isHost = !!room && room.hostId === userId

  const refreshPlayUrl = useCallback(async () => {
    if (roomCode) {
      await joinKaraokeRoom(roomCode)
    }
  }, [roomCode])

  // Registrar al usuario en Django antes de iniciar la escucha de Firebase.
  useEffect(() => {
    if (!roomCode || !userId) {
      return
    }

    let cancelled = false
    let unsubscribe: (() => void) | undefined

    async function connectRoom() {
      setStatus('loading')
      setRoom(null)

      try {
        await joinKaraokeRoom(roomCode)

        if (cancelled) {
          return
        }

        const roomRef = ref(db, `karaokeRooms/${roomCode}`)
        unsubscribe = onValue(
          roomRef,
          (snapshot) => {
            if (!snapshot.exists()) {
              setRoom(null)
              setStatus('not_found')
              return
            }

            const raw = snapshot.val() as RawRoom
            const normalized: KaraokeRoom = {
              ...raw,
              participants: Object.values(raw.participants ?? {}),
              lyricsTimestamps: Array.isArray(raw.lyricsTimestamps)
                ? raw.lyricsTimestamps
                : Object.values(raw.lyricsTimestamps ?? {}),
              volumes: raw.volumes,
            }

            setRoom(normalized)
            setStatus('ready')

            if (raw.hostId !== userId && audioRef.current) {
              if (raw.state === 'playing') {
                const drift = Math.abs(audioRef.current.currentTime - raw.currentTime)
                if (drift > 0.5) {
                  audioRef.current.currentTime = raw.currentTime
                }
                if (audioRef.current.paused) {
                  audioRef.current.play().catch(() => {})
                }
              }

              if (raw.state === 'ended' && !audioRef.current.paused) {
                audioRef.current.pause()
              }
              if (raw.state === 'paused' && !audioRef.current.paused) {
                audioRef.current.pause()
              }
              if (raw.state === 'paused') {
                audioRef.current.currentTime = raw.currentTime
              }
            }
          },
          () => {
            if (!cancelled) {
              setStatus('error')
            }
          }
        )
      } catch (error: unknown) {
        if (cancelled) {
          return
        }

        const responseStatus =
          typeof error === 'object' && error !== null && 'response' in error
            ? (
                error as {
                  response?: { status?: number }
                }
              ).response?.status
            : undefined

        setStatus(responseStatus === 404 ? 'not_found' : 'error')
      }
    }

    void connectRoom()

    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [roomCode, userId, audioRef])

  // Renueva la URL privada mientras la sala permanece abierta.
  useEffect(() => {
    if (!roomCode) return
    const interval = setInterval(() => {
      void joinKaraokeRoom(roomCode)
    }, 45 * 60 * 1000)
    return () => clearInterval(interval)
  }, [roomCode])

  // El anfitrión publica el tiempo de reproducción.
  useEffect(() => {
    if (syncRef.current) {
      clearInterval(syncRef.current)
    }

    if (!isHost || room?.state !== 'playing') {
      return
    }

    syncRef.current = setInterval(async () => {
      if (!audioRef.current) {
        return
      }

      try {
        await update(ref(db, `karaokeRooms/${roomCode}`), {
          currentTime: audioRef.current.currentTime,
        })
      } catch {
        // Se conservará el último tiempo conocido.
      }
    }, 1000)

    return () => {
      if (syncRef.current) {
        clearInterval(syncRef.current)
      }
    }
  }, [isHost, room?.state, roomCode, audioRef])

  async function startPlaying() {
    if (!isHost) {
      return
    }

    await update(ref(db, `karaokeRooms/${roomCode}`), {
      state: 'playing',
      startedAt: Date.now(),
      currentTime: room?.state === 'paused'
        ? (audioRef.current?.currentTime ?? room.currentTime)
        : 0,
    })
  }

  async function endRoom() {
    if (!isHost) {
      return
    }

    await update(ref(db, `karaokeRooms/${roomCode}`), { state: 'ended' })
    audioRef.current?.pause()
  }

  async function pausePlaying() {
    if (!isHost) return
    await update(ref(db, `karaokeRooms/${roomCode}`), {
      state: 'paused',
      currentTime: audioRef.current?.currentTime ?? room?.currentTime ?? 0,
    })
  }

  async function seekPlaying(currentTime: number) {
    if (!isHost) return
    await update(ref(db, `karaokeRooms/${roomCode}`), {
      currentTime: Math.max(0, currentTime),
    })
  }

  async function leaveRoom() {
    audioRef.current?.pause()

    if (isHost) {
      return
    }

    try {
      await update(ref(db, `karaokeRooms/${roomCode}`), {
        [`participants/${userId}`]: null,
        [`volumes/${userId}`]: null,
      })
    } catch {
      // El cierre de la página no depende de Firebase.
    }
  }

  const publishVolume = useCallback(
    async (level: number) => {
      if (!roomCode || !userId || !room) {
        return
      }

      try {
        await update(ref(db, `karaokeRooms/${roomCode}`), {
          [`volumes/${userId}`]: Math.round(level * 100) / 100,
        })
      } catch {
        // Ignorar errores transitorios del volumen.
      }
    },
    [roomCode, userId, room]
  )

  return {
    room,
    status,
    isHost,
    refreshPlayUrl,
    startPlaying,
    pausePlaying,
    seekPlaying,
    endRoom,
    leaveRoom,
    publishVolume,
  }
}
