import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Sparkles, TrendingUp } from 'lucide-react'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { Button } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { getSongPlayUrl } from '../../songs/api/songs.api'
import type { HomeSong } from '../../songs/components/home-song-card'
import { fetchForYouSongs, fetchTrendingSongs } from '../api/home.api'
import HomeSongRow, { type HomeRowState } from '../components/home-song-row'
import QuickToolsGrid from '../components/quick-tools-grid'

const INITIAL_ROW: HomeRowState = { songs: [], loading: true, error: false }

function SectionHeader({
  icon,
  title,
  subtitle,
}: {
  icon: ReactNode
  title: string
  subtitle: string
}) {
  return (
    <div className="mb-4 flex items-center gap-2.5">
      <div className="text-primary">{icon}</div>
      <div>
        <h2 className="text-lg font-bold text-white">{title}</h2>
        <p className="text-xs text-muted">{subtitle}</p>
      </div>
    </div>
  )
}

export default function InicioPage() {
  const navigate = useNavigate()
  const [trending, setTrending] = useState<HomeRowState>(INITIAL_ROW)
  const [forYou, setForYou] = useState<HomeRowState>(INITIAL_ROW)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const { track, isPlaying, playTrack, pause } = useGlobalAudioPlayer()

  useEffect(() => {
    fetchTrendingSongs()
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

    fetchForYouSongs()
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
      toast.error('No se pudo reproducir la canción')
    } finally {
      setLoadingId(null)
    }
  }

  const rowProps = { activeId: track?.id, isPlaying, loadingId, onPlay: handlePlay }

  return (
    <div className="min-h-full space-y-9 bg-surface px-4 pb-20 pt-6 text-white sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Inicio</h1>
          <p className="mt-1 text-sm text-muted">Crea, escucha y organiza tu música.</p>
        </div>

        <Button leftIcon={<Plus size={16} aria-hidden="true" />} onClick={() => navigate('/create')}>
          Crear canción
        </Button>
      </header>

      <QuickToolsGrid />

      <section>
        <SectionHeader
          icon={<TrendingUp size={20} aria-hidden="true" />}
          title="Tendencias"
          subtitle="Lo más escuchado de la comunidad"
        />
        <HomeSongRow
          row={trending}
          emptyTitle="Sin tendencias todavía"
          emptyDescription="Todavía no hay canciones públicas en la comunidad."
          emptyActionLabel="Explorar comunidad"
          emptyActionTo="/community"
          {...rowProps}
        />
      </section>

      <section>
        <SectionHeader
          icon={<Sparkles size={20} aria-hidden="true" />}
          title="Para ti"
          subtitle="Según tus géneros y estilos favoritos"
        />
        <HomeSongRow
          row={forYou}
          emptyTitle="Aún sin recomendaciones"
          emptyDescription="Crea canciones con descripción libre para que conozcamos tus gustos."
          emptyActionLabel="Crear primera canción"
          emptyActionTo="/create"
          {...rowProps}
        />
      </section>
    </div>
  )
}
