import axios from 'axios'
import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, UsersRound } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { Badge, Button } from '../../../components/ui'
import { isFirebaseConfigured } from '../../../lib/env'
import { refreshAuthBalance } from '../../../store/active-jobs.store'
import { useAuthStore } from '../../../store/auth.store'
import { toast } from '../../../store/toast.store'
import type { KaraokePlayData } from '../../../types'
import { createKaraokeRoom, getKaraokePlayData } from '../api/karaoke.api'
import KaraokeLyrics from '../components/karaoke-lyrics'
import KaraokePlayerFooter from '../components/karaoke-player-footer'

const ROOM_COST = 1

export default function KaraokePlayerPage() {
  const { karaokeId } = useParams<{ karaokeId: string }>()
  const navigate = useNavigate()
  const creditBalance = useAuthStore((state) => state.user?.credit_balance ?? 0)
  const firebaseReady = isFirebaseConfigured()

  const audioRef = useRef<HTMLAudioElement>(null)
  const lyricsScrollRef = useRef<HTMLDivElement>(null)
  const [playData, setPlayData] = useState<KaraokePlayData | null>(null)
  const [loading, setLoading] = useState(true)
  const [roomError, setRoomError] = useState<string | null>(null)
  const [creatingRoom, setCreatingRoom] = useState(false)

  useEffect(() => {
    if (!karaokeId) {
      return
    }
    setLoading(true)
    getKaraokePlayData(karaokeId)
      .then(setPlayData)
      .catch(() => toast.error('No se pudo cargar el reproductor de karaoke'))
      .finally(() => setLoading(false))
  }, [karaokeId])

  async function handleCreateRoom() {
    if (!firebaseReady || !karaokeId || !playData || creatingRoom) {
      return
    }
    setRoomError(null)
    if (creditBalance < ROOM_COST) {
      setRoomError(`Necesitas ${ROOM_COST} crédito para crear una sala.`)
      return
    }
    setCreatingRoom(true)
    try {
      const result = await createKaraokeRoom(karaokeId)
      void refreshAuthBalance()
      navigate(`/karaoke/room/${result.room_code}`)
    } catch (error: unknown) {
      const message = axios.isAxiosError(error) ? error.response?.data?.detail : null
      setRoomError(typeof message === 'string' ? message : 'No se pudo crear la sala de karaoke.')
    } finally {
      setCreatingRoom(false)
    }
  }

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-gradient-to-br from-night to-card text-white">
      <header className="z-10 flex shrink-0 items-center justify-between gap-3 px-6 py-4">
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<ArrowLeft size={14} />}
          onClick={() => navigate('/karaoke')}
        >
          Catálogo
        </Button>

        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            costCredits={ROOM_COST}
            leftIcon={<UsersRound size={14} />}
            loading={creatingRoom}
            disabled={!firebaseReady || !playData || creatingRoom}
            title={
              firebaseReady
                ? 'Crear una sala compartida (1 crédito)'
                : 'Las salas en vivo requieren configuración en tiempo real. Disponible próximamente.'
            }
            onClick={() => void handleCreateRoom()}
          >
            Crear sala
          </Button>
          {!firebaseReady && <Badge variant="warning">Próximamente</Badge>}
        </div>
      </header>

      {!firebaseReady && (
        <p className="z-10 mx-6 mb-1 rounded-lg border border-warning/30 bg-warning/10 px-3.5 py-2 text-xs text-warning">
          Las salas compartidas en vivo estarán disponibles próximamente. No se descontarán créditos.
        </p>
      )}

      {roomError && (
        <div
          role="alert"
          className="z-10 mx-6 mb-1 rounded-lg border border-error-border bg-error-soft px-4 py-2.5 text-xs font-medium text-error"
        >
          {roomError}
        </div>
      )}

      <div className="relative flex-1 overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-28 bg-gradient-to-b from-night to-transparent" />
        {loading && <p className="mt-8 text-center text-sm text-muted">Cargando karaoke...</p>}
        {!loading && playData && playData.lyrics_timestamps.length > 0 && (
          <div
            ref={lyricsScrollRef}
            className="scrollbar-hidden flex h-full flex-col items-center overflow-y-auto px-6 pb-[16vh] pt-[30vh] text-center sm:px-16"
          >
            <KaraokeLyrics
              timestamps={playData.lyrics_timestamps}
              audioRef={audioRef}
              scrollRef={lyricsScrollRef}
            />
          </div>
        )}
        {!loading && playData && playData.lyrics_timestamps.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center px-8 text-center text-muted">
            <p className="text-base font-semibold text-white/80">
              Las letras no están disponibles para esta pista.
            </p>
            <p className="mt-1.5 max-w-sm text-xs">
              Es posible que la canción sea instrumental o no se haya detectado voz clara.
            </p>
          </div>
        )}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-28 bg-gradient-to-t from-card to-transparent" />
      </div>

      <KaraokePlayerFooter
        audioRef={audioRef}
        audioUrl={playData?.play_url ?? null}
        songTitle={playData?.song_title ?? 'Karaoke'}
      />
    </div>
  )
}
