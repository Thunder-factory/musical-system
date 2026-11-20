import { useCallback, useEffect, useRef, useState } from 'react'
import { LoaderCircle } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { Button } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import RoomParticipantsPanel from '../components/room-participants-panel'
import RoomStage from '../components/room-stage'
import { useKaraokeRoom } from '../hooks/useKaraokeRoom'
import { useMicVolume } from '../hooks/useMicVolume'

export default function KaraokeRoomPage() {
  const { roomCode } = useParams<{ roomCode: string }>()
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const prevRoomStateRef = useRef<string | undefined>(undefined)

  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  const {
    room,
    status,
    isHost,
    startPlaying,
    pausePlaying,
    seekPlaying,
    endRoom,
    leaveRoom,
    publishVolume,
    refreshPlayUrl,
  } = useKaraokeRoom({ roomCode: roomCode!, userId: user?.id ?? '', audioRef })

  const ownVolume = useMicVolume(room?.state === 'ended')

  useEffect(() => {
    if (room?.state === 'playing' && prevRoomStateRef.current !== 'playing') {
      prevRoomStateRef.current = 'playing'
      if (audioRef.current?.paused) {
        audioRef.current.currentTime = 0
        audioRef.current.play().catch(() => {})
      }
    } else if (room?.state) {
      prevRoomStateRef.current = room.state
    }
  }, [room?.state])

  useEffect(() => {
    if (roomCode) {
      void publishVolume(ownVolume)
    }
  }, [ownVolume, publishVolume, roomCode])

  const handleEnded = useCallback(() => {
    setIsPlaying(false)
    if (isHost) {
      void endRoom()
    }
  }, [endRoom, isHost])

  function handleLeave() {
    leaveRoom().finally(() => navigate('/karaoke'))
  }

  function togglePlay() {
    if (!audioRef.current) {
      return
    }
    if (isPlaying) {
      void pausePlaying()
      audioRef.current.pause()
    } else {
      void startPlaying()
      void audioRef.current.play()
    }
  }

  function skip(secs: number) {
    if (!audioRef.current) {
      return
    }
    const next = Math.max(0, Math.min(duration, currentTime + secs))
    audioRef.current.currentTime = next
    void seekPlaying(next)
  }

  function seekTo(nextTime: number) {
    if (!audioRef.current) {
      return
    }
    audioRef.current.currentTime = nextTime
    void seekPlaying(nextTime)
  }

  if (status === 'not_found' || status === 'error' || room?.state === 'ended') {
    const title =
      status === 'not_found'
        ? 'Sala no encontrada'
        : status === 'error'
          ? 'Error de conexión'
          : 'La sala terminó'
    const message =
      status === 'not_found'
        ? `El código "${roomCode}" no corresponde a ninguna sala activa.`
        : status === 'error'
          ? 'No se pudo conectar a la sala. Inténtalo de nuevo.'
          : 'El anfitrión cerró la sesión de karaoke.'
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-surface p-8 text-center">
        <p className="text-lg font-bold text-white">{title}</p>
        <p className="max-w-xs text-sm text-muted">{message}</p>
        <Button variant="primary" onClick={() => navigate('/karaoke')}>
          Volver al catálogo
        </Button>
      </div>
    )
  }

  if (!room) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-surface p-8 text-center">
        <LoaderCircle size={28} className="animate-spin text-primary" aria-hidden="true" />
        <p className="text-sm text-muted">Conectando a la sala...</p>
      </div>
    )
  }

  if (room.state === 'waiting') {
    return (
      <RoomParticipantsPanel
        room={room}
        roomCode={roomCode!}
        isHost={isHost}
        userId={user?.id}
        ownVolume={ownVolume}
        onBack={isHost ? () => navigate('/karaoke') : handleLeave}
        onStart={() => void startPlaying()}
      />
    )
  }

  return (
    <>
      {room.playUrl && (
        <audio
          ref={audioRef}
          src={room.playUrl}
          onError={() => void refreshPlayUrl()}
          onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime ?? 0)}
          onDurationChange={() => setDuration(audioRef.current?.duration ?? 0)}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={handleEnded}
        />
      )}
      <RoomStage
        room={room}
        roomCode={roomCode!}
        isHost={isHost}
        userId={user?.id}
        ownVolume={ownVolume}
        audioRef={audioRef}
        isPlaying={isPlaying}
        currentTime={currentTime}
        duration={duration}
        onTogglePlay={togglePlay}
        onSkip={skip}
        onSeekTo={seekTo}
        onEndRoom={() => void endRoom()}
        onLeave={handleLeave}
      />
    </>
  )
}
