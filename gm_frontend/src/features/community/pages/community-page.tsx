import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Flame, Music2, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button, EmptyState } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import type { LibrarySong } from '../../songs/api/songs.api'
import LyricsView from '../../songs/components/lyrics-view'
import {
  getCommunityFeed,
  getCommunityStats,
  getTrending,
  type CommunitySong,
  type CommunityStats,
} from '../api/community.api'
import CommunityFilters from '../components/community-filters'
import CommunitySongGrid from '../components/community-song-grid'
import CommunityStatsRow from '../components/community-stats-row'
import { useCommunityPlayback } from '../hooks/useCommunityPlayback'

export default function CommunityPage() {
  const navigate = useNavigate()
  const [songs, setSongs] = useState<CommunitySong[]>([])
  const [stats, setStats] = useState<CommunityStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [page, setPage] = useState(1)
  const [hasNext, setHasNext] = useState(false)
  const [search, setSearch] = useState('')
  const [activeTag, setActiveTag] = useState('Todos')
  const {
    audioRef,
    globalTrack,
    isPlaying,
    loadingSongId,
    activeSong,
    showLyrics,
    setShowLyrics,
    handlePlay,
  } = useCommunityPlayback()

  const loadFeed = useCallback(async (p: number, tag: string, q: string, append = false) => {
    if (p === 1) {
      setLoading(true)
    } else {
      setLoadingMore(true)
    }
    try {
      if (tag === 'Trending') {
        const trending = await getTrending()
        const query = q.trim().toLowerCase()
        setSongs(
          query
            ? trending.filter(
                (s) =>
                  s.title.toLowerCase().includes(query) ||
                  s.user_name.toLowerCase().includes(query)
              )
            : trending
        )
        setHasNext(false)
        setPage(1)
      } else {
        const res = await getCommunityFeed({
          search: q,
          tag: tag === 'Todos' ? '' : tag,
          page: p,
        })
        setSongs((prev) => (append ? [...prev, ...res.results] : res.results))
        setHasNext(res.has_next)
        setPage(p)
      }
    } catch {
      toast.error('No se pudieron cargar las canciones de la comunidad')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [])

  useEffect(() => {
    void loadFeed(1, 'Todos', '')
    getCommunityStats().then(setStats).catch(() => {})
  }, [loadFeed])

  function handleSearchSubmit(e: FormEvent) {
    e.preventDefault()
    void loadFeed(1, activeTag, search)
  }

  return (
    <div className="min-h-full px-6 pb-20 pt-7 text-white sm:px-8">
      <div className="mb-6 flex flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Comunidad</h1>
            <p className="mt-1 text-sm text-muted">
              Explora y escucha creaciones de otros usuarios.
            </p>
          </div>
          <Button
            variant="primary"
            leftIcon={<Plus size={15} />}
            onClick={() => navigate('/library')}
          >
            Publicar canción
          </Button>
        </div>

        <CommunityFilters
          search={search}
          activeTag={activeTag}
          onSearchChange={setSearch}
          onSearchSubmit={handleSearchSubmit}
          onTagChange={(tag) => {
            setActiveTag(tag)
            void loadFeed(1, tag, search)
          }}
        />
      </div>

      <CommunityStatsRow stats={stats} />

      {activeTag === 'Trending' && (
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-primary">
          <Flame size={16} aria-hidden="true" />
          <span>Canciones en tendencia en las últimas 48 horas</span>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-96 animate-pulse rounded-2xl bg-card-hover" />
          ))}
        </div>
      ) : songs.length === 0 ? (
        <EmptyState
          icon={<Music2 size={24} />}
          title="No se encontraron canciones"
          description="Prueba con otro término o filtro, o publica una canción desde tu biblioteca."
          actionLabel="Ir a mi biblioteca"
          actionTo="/library"
        />
      ) : (
        <>
          <CommunitySongGrid
            songs={songs}
            activeTrackId={globalTrack?.id}
            isPlaying={isPlaying}
            loadingSongId={loadingSongId}
            onPlay={(song, coverUrl) => void handlePlay(song, coverUrl)}
          />
          {hasNext && (
            <div className="mt-8 flex justify-center">
              <Button
                variant="secondary"
                loading={loadingMore}
                onClick={() => void loadFeed(page + 1, activeTag, search, true)}
              >
                {loadingMore ? 'Cargando...' : 'Ver más'}
              </Button>
            </div>
          )}
        </>
      )}

      {showLyrics && activeSong && (
        <LyricsView
          song={activeSong as unknown as LibrarySong}
          audioRef={audioRef}
          onClose={() => setShowLyrics(false)}
        />
      )}
    </div>
  )
}
