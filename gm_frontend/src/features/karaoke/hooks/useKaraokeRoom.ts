import { useCallback, useEffect, useRef, useState } from 'react'
import { onValue, ref, update } from 'firebase/database'

// @ts-expect-error — firebase.js es JS puro; Vite resuelve el módulo correctamente
import { db } from '../../../firebase.js'
import type { KaraokeRoom } from '../../../types'
import { joinKaraokeRoom } from '../api/karaoke.api'
import { getResponseStatus, normalizeRoom, syncGuestAudio, type RawRoom } from './karaoke-room-sync'

interface Params {
  roomCode: string
  userId: string
  audioRef: React.RefObject<HTMLAudioElement | null>
}

export function useKaraokeRoom({ roomCode, userId, audioRef }: Params) {
  const [room, setRoom] = useState<KaraokeRoom | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'not_found' | 'error'>('loading')
  const syncRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isHost = Boolean(room && room.hostId === userId)

  const refreshPlayUrl = useCallback(async () => {
    if (roomCode) {
      await joinKaraokeRoom(roomCode)
    }
  }, [roomCode])

  useEffect(() => {
    if (!roomCode || !userId) {
      return
    }
    let cancelled = false
    let unsubscribe: (() => void) | undefined

    async function connectRoom() {
      if (!db) {
        setStatus('error')
        return
      }
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
            setRoom(normalizeRoom(raw))
            setStatus('ready')
            syncGuestAudio(raw, userId, audioRef.current)
          },
          () => !cancelled && setStatus('error')
        )
      } catch (err: unknown) {
        if (!cancelled) {
          setStatus(getResponseStatus(err) === 404 ? 'not_found' : 'error')
        }
      }
    }

    void connectRoom()
    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [roomCode, userId, audioRef])

  useEffect(() => {
    if (!roomCode) {
      return
    }
    const interval = setInterval(() => void joinKaraokeRoom(roomCode), 45 * 60 * 1000)
    return () => clearInterval(interval)
  }, [roomCode])

  useEffect(() => {
    if (syncRef.current) {
      clearInterval(syncRef.current)
    }
    if (!isHost || room?.state !== 'playing' || !db) {
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
        // Conserva el último tiempo conocido.
      }
    }, 1000)
    return () => {
      if (syncRef.current) {
        clearInterval(syncRef.current)
      }
    }
  }, [isHost, room?.state, roomCode, audioRef])

  async function startPlaying() {
    if (!isHost || !db) {
      return
    }
    await update(ref(db, `karaokeRooms/${roomCode}`), {
      state: 'playing',
      startedAt: Date.now(),
      currentTime:
        room?.state === 'paused' ? (audioRef.current?.currentTime ?? room.currentTime) : 0,
    })
  }

  async function endRoom() {
    if (!isHost || !db) {
      return
    }
    await update(ref(db, `karaokeRooms/${roomCode}`), { state: 'ended' })
    audioRef.current?.pause()
  }

  async function pausePlaying() {
    if (!isHost || !db) {
      return
    }
    await update(ref(db, `karaokeRooms/${roomCode}`), {
      state: 'paused',
      currentTime: audioRef.current?.currentTime ?? room?.currentTime ?? 0,
    })
  }

  async function seekPlaying(currentTime: number) {
    if (isHost && db) {
      await update(ref(db, `karaokeRooms/${roomCode}`), { currentTime: Math.max(0, currentTime) })
    }
  }

  async function leaveRoom() {
    audioRef.current?.pause()
    if (isHost || !db) {
      return
    }
    try {
      await update(ref(db, `karaokeRooms/${roomCode}`), {
        [`participants/${userId}`]: null,
        [`volumes/${userId}`]: null,
      })
    } catch {
      // Ignorar errores al salir.
    }
  }

  const publishVolume = useCallback(
    async (level: number) => {
      if (!roomCode || !userId || !room || !db) {
        return
      }
      try {
        await update(ref(db, `karaokeRooms/${roomCode}`), {
          [`volumes/${userId}`]: Math.round(level * 100) / 100,
        })
      } catch {
        // Ignorar errores transitorios de volumen.
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
