// src/pages/cliente/Inicio.tsx
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles, TrendingUp, Coins } from 'lucide-react'
import { useAuthStore } from '../../store/auth.store'
import { getTrending } from '../../api/modules/community.api'
import { getForYou } from '../../api/modules/recommendations.api'
import { getSongPlayUrl } from '../../api/modules/songs.api'
import { useGlobalAudioPlayer } from '../../components/player/use-global-audio-player'
import HomeSongCard from '../../components/song/home-song-card'
import type { HomeSong } from '../../components/song/home-song-card'

type RowState = { songs: HomeSong[]; loading: boolean; error: boolean }

const INITIAL_ROW: RowState = { songs: [], loading: true, error: false }

function SongRow({
  row,
  emptyText,
  activeId,
  isPlaying,
  loadingId,
  onPlay,
}: {
  row: RowState
  emptyText: string
  activeId?: string
  isPlaying: boolean
  loadingId: string | null
  onPlay: (song: HomeSong) => void
}) {
  if (row.loading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="shrink-0 w-[200px] h-[280px] rounded-2xl bg-card-hover animate-pulse"
          />
        ))}
      </div>
    )
  }

  if (row.error || row.songs.length === 0) {
    return (
      <div className="rounded-2xl border border-card-hover bg-card px-5 py-6 text-sm text-muted">
        {row.error ? 'No se pudieron cargar las canciones. Intenta de nuevo más tarde.' : emptyText}
      </div>
    )
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {row.songs.map((song) => (
        <HomeSongCard
          key={song.id}
          song={song}
          onPlay={onPlay}
          isPlaying={activeId === `song:${song.id}` && isPlaying}
          isLoading={loadingId === song.id}
        />
      ))}
    </div>
  )
}

function SectionHeader({
  icon,
  title,
  subtitle,
}: {
  icon: ReactNode
  title: string
  subtitle?: string
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <div className="text-primary-hover">{icon}</div>
      <div>
        <h2 className="text-lg font-bold text-white">{title}</h2>
        {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
      </div>
    </div>
  )
}

export default function Inicio() {
  const { user } = useAuthStore()
  const credits = user?.credit_balance ?? 0
  const [trending, setTrending] = useState<RowState>(INITIAL_ROW)
  const [forYou, setForYou] = useState<RowState>(INITIAL_ROW)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const { track, isPlaying, playTrack, pause } = useGlobalAudioPlayer()

  useEffect(() => {
    getTrending()
      .then((songs) =>
        setTrending({
          loading: false,
          error: false,
          songs: songs.map((s) => ({
            id: s.id,
            title: s.title || 'Sin título',
            subtitle: s.user_name,
            tags: s.tags.map((t) => t.name),
            thumbnailKey: s.thumbnail_s3_key,
          })),
        })
      )
      .catch(() => setTrending({ songs: [], loading: false, error: true }))

    getForYou()
      .then((songs) =>
        setForYou({
          loading: false,
          error: false,
          songs: songs.map((s) => ({
            id: s.id,
            title: s.title || 'Sin título',
            subtitle: s.genre ?? s.mood ?? 'Recomendada para ti',
            tags: s.tags?.map((t) => t.name) ?? [],
            thumbnailUrl: s.thumbnail_url,
            thumbnailKey: s.thumbnail_s3_key,
          })),
        })
      )
      .catch(() => setForYou({ songs: [], loading: false, error: true }))
  }, [])

  async function handlePlay(song: HomeSong) {
    const trackId = `song:${song.id}`
    if (track?.id === trackId) {
      if (isPlaying) {
        pause()
      } else {
        playTrack(track)
      }
      return
    }
    setLoadingId(song.id)
    try {
      const url = await getSongPlayUrl(song.id)
      playTrack({ id: trackId, audioUrl: url, title: song.title, subtitle: song.subtitle })
    } catch {
      // Si no hay URL de audio la tarjeta queda en su estado normal.
    } finally {
      setLoadingId(null)
    }
  }

  const rowProps = { activeId: track?.id, isPlaying, loadingId, onPlay: handlePlay }

  return (
    <div className="min-h-full bg-night text-white px-8 py-8 space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold">Inicio</h1>
          <p className="text-sm text-muted">Crea, escucha y organiza tu música.</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-full bg-card border border-card-hover px-4 py-2">
            <Coins size={16} className="text-primary-hover" />
            <span className="text-sm font-semibold">{credits} créditos</span>
          </div>

          <Link
            to="/create"
            className="rounded-full bg-primary hover:bg-primary-light text-black text-sm font-bold px-5 py-2 transition-colors"
          >
            + Crear canción
          </Link>
        </div>
      </div>

      <section>
        <SectionHeader
          icon={<TrendingUp size={20} />}
          title="Tendencias"
          subtitle="Lo más escuchado de la comunidad"
        />
        <SongRow
          row={trending}
          emptyText="Todavía no hay canciones públicas en la comunidad."
          {...rowProps}
        />
      </section>

      <section>
        <SectionHeader
          icon={<Sparkles size={20} />}
          title="Para ti"
          subtitle="Según tus géneros y estilos favoritos"
        />
        <SongRow
          row={forYou}
          emptyText="Crea canciones con descripción libre para recibir recomendaciones."
          {...rowProps}
        />
      </section>
    </div>
  )
}
