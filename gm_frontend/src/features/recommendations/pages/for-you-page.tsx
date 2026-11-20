import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, Sparkles } from 'lucide-react'

import { Badge, Button, EmptyState } from '../../../components/ui'
import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { toast } from '../../../store/toast.store'
import { getSongPlayUrl, toggleSongLike, type LibrarySong } from '../../songs/api/songs.api'
import SongCard from '../../songs/components/song-card'
import {
  getForYou,
  getSuggestedTags,
  type SuggestedTag,
} from '../api/recommendations.api'

export default function ForYouPage() {
  const [songs, setSongs] = useState<LibrarySong[]>([])
  const [tags, setTags] = useState<SuggestedTag[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingSongId, setLoadingSongId] = useState<string | null>(null)
  const { track: globalTrack, isPlaying, playTrack, pause } = useGlobalAudioPlayer()

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)
    try {
      const [s, t] = await Promise.all([getForYou(), getSuggestedTags()])
      setSongs(s)
      setTags(t)
    } catch {
      const msg = 'No se pudieron cargar tus recomendaciones.'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void fetchData()
  }, [fetchData])

  async function handlePlay(song: LibrarySong) {
    const trackId = `song:${song.id}`
    if (globalTrack?.id === trackId) {
      if (isPlaying) {
        pause()
      } else {
        playTrack(globalTrack)
      }
      return
    }
    setLoadingSongId(song.id)
    try {
      const url = song.play_url ?? (await getSongPlayUrl(song.id))
      playTrack({
        id: trackId,
        audioUrl: url,
        title: song.title ?? 'Sin título',
        subtitle: song.genre ?? undefined,
        coverUrl: song.thumbnail_url,
      })
    } catch {
      toast.error('No se pudo reproducir la canción')
    } finally {
      setLoadingSongId(null)
    }
  }

  async function handleLike(songId: string) {
    try {
      await toggleSongLike(songId)
    } catch {
      toast.error('No se pudo registrar tu me gusta')
    }
  }

  if (loading) {
    return (
      <div className="min-h-full px-6 pb-20 pt-7 text-white sm:px-8">
        <div className="mb-6">
          <h1 className="text-3xl font-bold tracking-tight">Para ti</h1>
          <p className="mt-1 text-sm text-muted">Cargando recomendaciones...</p>
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-80 animate-pulse rounded-xl bg-card-hover" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-full px-6 pb-20 pt-7 text-white sm:px-8">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Para ti</h1>
          <p className="mt-1 text-sm text-muted">Descubre canciones según tus gustos.</p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          loading={refreshing}
          leftIcon={<RefreshCw size={14} />}
          onClick={() => void fetchData(true)}
        >
          {refreshing ? 'Actualizando...' : 'Actualizar'}
        </Button>
      </header>

      {error && (
        <div
          role="alert"
          className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          <span>{error}</span>
          <Button variant="secondary" size="sm" onClick={() => void fetchData(true)}>
            Reintentar
          </Button>
        </div>
      )}

      {tags.length > 0 && (
        <section className="mb-7">
          <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-muted">
            Tus géneros destacados
          </p>
          <div className="flex flex-wrap gap-2">
            {tags.map((t) => (
              <Badge key={t.id} variant="primary" className="px-3 py-1 text-xs">
                {t.name}
              </Badge>
            ))}
          </div>
        </section>
      )}

      {songs.length > 0 ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
          {songs.map((song) => (
            <SongCard
              key={song.id}
              song={song}
              onPlay={(s) => void handlePlay(s)}
              onLike={(id) => void handleLike(id)}
              isActive={globalTrack?.id === `song:${song.id}`}
              isPlaying={globalTrack?.id === `song:${song.id}` && isPlaying}
              isLoading={loadingSongId === song.id}
            />
          ))}
        </div>
      ) : (
        !error && (
          <EmptyState
            icon={<Sparkles size={24} />}
            title="Sin recomendaciones todavía"
            description="Crea canciones o explora la comunidad para descubrir pistas afines a tu estilo."
            actionLabel="Crear una canción"
            actionTo="/create"
          />
        )
      )}
    </div>
  )
}
