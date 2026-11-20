import { useRef } from 'react'
import { LogOut, Pause, Play, RotateCcw, RotateCw, UsersRound } from 'lucide-react'

import { Button } from '../../../components/ui'
import type { KaraokeParticipant, KaraokeRoom } from '../../../types'
import KaraokeLyrics from './karaoke-lyrics'
import { ParticipantBubble } from './room-participants-panel'

function formatTime(s: number): string {
  if (!Number.isFinite(s) || s < 0) {
    return '0:00'
  }
  const m = Math.floor(s / 60)
  return `${m}:${Math.floor(s % 60).toString().padStart(2, '0')}`
}

interface RoomStageProps {
  room: KaraokeRoom
  roomCode: string
  isHost: boolean
  userId?: string
  ownVolume: number
  audioRef: React.RefObject<HTMLAudioElement | null>
  isPlaying: boolean
  currentTime: number
  duration: number
  onTogglePlay: () => void
  onSkip: (seconds: number) => void
  onSeekTo: (time: number) => void
  onEndRoom: () => void
  onLeave: () => void
}

export default function RoomStage({
  room,
  roomCode,
  isHost,
  userId,
  ownVolume,
  audioRef,
  isPlaying,
  currentTime,
  duration,
  onTogglePlay,
  onSkip,
  onSeekTo,
  onEndRoom,
  onLeave,
}: RoomStageProps) {
  const lyricsScrollRef = useRef<HTMLDivElement>(null)

  function volumeOf(p: KaraokeParticipant): number {
    return p.userId === userId ? ownVolume : (room.volumes?.[p.userId] ?? 0)
  }

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-gradient-to-br from-night to-card text-white">
      <header className="z-10 flex shrink-0 items-center justify-between gap-3 px-5 py-3.5">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-primary-border bg-primary-soft px-3 py-1 text-xs font-bold tracking-wider text-primary-hover">
          <UsersRound size={12} aria-hidden="true" />
          {roomCode}
        </div>

        <div className="flex items-center gap-2">
          {room.participants.map((p) => (
            <ParticipantBubble
              key={p.userId}
              participant={p}
              isHost={p.userId === room.hostId}
              volume={volumeOf(p)}
              size={38}
            />
          ))}
          {isHost ? (
            <Button variant="danger" size="sm" onClick={onEndRoom}>
              Terminar
            </Button>
          ) : (
            <Button variant="danger" size="sm" onClick={onLeave}>
              Salir
            </Button>
          )}
        </div>
      </header>

      <div className="relative flex-1 overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-28 bg-gradient-to-b from-night to-transparent" />
        <div
          ref={lyricsScrollRef}
          className="scrollbar-hidden flex h-full flex-col items-center overflow-y-auto px-6 pb-[16vh] pt-[30vh] text-center sm:px-16"
        >
          <KaraokeLyrics
            timestamps={room.lyricsTimestamps ?? []}
            audioRef={audioRef}
            scrollRef={lyricsScrollRef}
          />
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-28 bg-gradient-to-t from-card to-transparent" />
      </div>

      {isHost ? (
        <footer className="z-10 flex shrink-0 flex-col gap-2.5 px-7 pb-5 pt-2.5">
          <div className="flex items-center justify-between gap-3">
            <span className="max-w-[65%] truncate text-sm font-semibold text-white/80">
              {room.songTitle}
            </span>
            <span className="shrink-0 text-xs tabular-nums text-muted">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          <input
            type="range"
            min={0}
            max={duration > 0 ? duration : 100}
            step={0.1}
            value={Math.min(currentTime, duration || 100)}
            disabled={duration <= 0}
            aria-label="Progreso de reproducción"
            onChange={(e) => onSeekTo(Number(e.target.value))}
            className="h-1.5 w-full cursor-pointer accent-primary"
          />

          <div className="flex items-center justify-center gap-4">
            <button
              type="button"
              onClick={() => onSkip(-10)}
              aria-label="Retroceder 10 segundos"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-card-hover text-white/80 transition-colors hover:bg-border-strong hover:text-white"
            >
              <RotateCcw size={15} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={onTogglePlay}
              aria-label={isPlaying ? 'Pausar' : 'Reproducir'}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-primary text-black transition-transform hover:scale-105 hover:bg-primary-hover"
            >
              {isPlaying ? (
                <Pause size={18} fill="currentColor" aria-hidden="true" />
              ) : (
                <Play size={18} fill="currentColor" aria-hidden="true" />
              )}
            </button>
            <button
              type="button"
              onClick={() => onSkip(10)}
              aria-label="Adelantar 10 segundos"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-card-hover text-white/80 transition-colors hover:bg-border-strong hover:text-white"
            >
              <RotateCw size={15} aria-hidden="true" />
            </button>
          </div>
        </footer>
      ) : (
        <footer className="z-10 flex shrink-0 flex-col items-center gap-2.5 px-4 pb-5 pt-3">
          <p className="text-xs text-muted">Sincronizado con {room.hostName}</p>
          <Button
            variant="danger"
            size="sm"
            leftIcon={<LogOut size={13} />}
            onClick={onLeave}
          >
            Abandonar sala
          </Button>
        </footer>
      )}
    </div>
  )
}
