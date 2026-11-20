import { useState } from 'react'
import { ArrowLeft, Check, Copy, Mic2 } from 'lucide-react'

import { Badge, Button } from '../../../components/ui'
import type { KaraokeParticipant, KaraokeRoom } from '../../../types'

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

export function ParticipantBubble({
  participant,
  isHost,
  volume = 0,
  size = 80,
}: {
  participant: KaraokeParticipant
  isHost: boolean
  volume?: number
  size?: number
}) {
  const v = Math.min(1, volume * 4)
  const ringOpacity = 0.15 + v * 0.55
  const ringSpread = size <= 48 ? 2 + v * 6 : 2 + v * 10
  const glow = size <= 48 ? v * 16 : v * 28

  const ringStyle = {
    width: size,
    height: size,
    fontSize: Math.round(size * (size <= 48 ? 0.34 : 0.27)),
    boxShadow: `0 0 0 ${ringSpread}px rgb(var(--color-success-rgb) / ${ringOpacity}), 0 0 ${glow}px rgb(var(--color-success-rgb) / ${v * 0.45})`,
  }

  if (size <= 48) {
    return (
      <div
        title={participant.userName}
        className="flex shrink-0 items-center justify-center rounded-full bg-[var(--gradient-primary)] font-bold text-black transition-shadow"
        style={ringStyle}
      >
        {getInitials(participant.userName)}
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="flex shrink-0 items-center justify-center rounded-full bg-[var(--gradient-primary)] font-bold text-black transition-shadow"
        style={ringStyle}
      >
        {getInitials(participant.userName)}
      </div>
      <span className="max-w-[96px] truncate text-center text-xs font-semibold text-white">
        {participant.userName}
      </span>
      {isHost && <Badge variant="primary">Anfitrión</Badge>}
    </div>
  )
}

interface RoomParticipantsPanelProps {
  room: KaraokeRoom
  roomCode: string
  isHost: boolean
  userId?: string
  ownVolume: number
  onBack: () => void
  onStart: () => void
}

export default function RoomParticipantsPanel({
  room,
  roomCode,
  isHost,
  userId,
  ownVolume,
  onBack,
  onStart,
}: RoomParticipantsPanelProps) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(roomCode).catch(() => {})
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  function volumeOf(p: KaraokeParticipant): number {
    if (p.userId === userId) {
      return ownVolume
    }
    return room.volumes?.[p.userId] ?? 0
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-surface">
      <div className="mx-auto flex w-full max-w-lg flex-col gap-6 px-7 py-8">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 self-start text-xs font-semibold text-muted transition-colors hover:text-white"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          {isHost ? 'Volver' : 'Abandonar sala'}
        </button>

        <div className="space-y-1.5">
          <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-muted">
            Código de sala
          </span>
          <div className="flex items-center gap-3">
            <span className="text-3xl font-extrabold tracking-[0.1em] text-white sm:text-4xl">
              {roomCode}
            </span>
            <Button
              variant="secondary"
              size="sm"
              leftIcon={copied ? <Check size={13} /> : <Copy size={13} />}
              onClick={handleCopy}
            >
              {copied ? 'Copiado' : 'Copiar'}
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2.5 rounded-xl bg-card-hover px-3.5 py-3">
          <Mic2 size={18} className="shrink-0 text-primary" aria-hidden="true" />
          <span className="truncate text-sm font-semibold text-white">{room.songTitle}</span>
        </div>

        <div className="space-y-3.5">
          <span className="text-xs font-bold uppercase tracking-[0.1em] text-muted">
            Participantes ({room.participants.length})
          </span>
          <div className="flex flex-wrap justify-center gap-6 py-2">
            {room.participants.map((p) => (
              <ParticipantBubble
                key={p.userId}
                participant={p}
                isHost={p.userId === room.hostId}
                volume={volumeOf(p)}
                size={96}
              />
            ))}
          </div>
        </div>

        {isHost ? (
          <Button variant="primary" size="lg" className="w-full" onClick={onStart}>
            Empezar Karaoke
          </Button>
        ) : (
          <div className="flex items-center gap-2.5 rounded-xl border border-primary-border bg-primary-soft px-4 py-3.5 text-sm font-medium text-primary-hover">
            <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-primary" />
            Esperando a que {room.hostName} inicie la canción...
          </div>
        )}
      </div>
    </div>
  )
}
