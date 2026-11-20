import { useContext, useEffect, useRef, useState } from 'react'
import { ListMusic, Pause, Play } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { GlobalAudioContext } from '../../../components/player/global-audio-context'
import { Badge, Button, EmptyState } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import { toast } from '../../../store/toast.store'
import { getSongPlayUrl } from '../../songs/api/songs.api'
import {
  getPlaylistCoverUrl,
  getPublicPlaylist,
  type Playlist,
  type PlaylistSongItem,
} from '../api/playlists.api'
import PlaylistSongRow from '../components/playlist-song-row'

export default function PublicPlaylistPage() {
  const { token } = useParams<{ token: string }>()
  const accessToken = useAuthStore((s) => s.accessToken)
  const globalAudio = useContext(GlobalAudioContext)
  const localAudioRef = useRef<HTMLAudioElement>(null)

  const [playlist, setPlaylist] = useState<Playlist | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeSongId, setActiveSongId] = useState<string | null>(null)
  const [localPlaying, setLocalPlaying] = useState(false)
  const [localUrl, setLocalUrl] = useState<string | null>(null)
  const [loadingPlayId, setLoadingPlayId] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setError('Enlace inválido.')
      setLoading(false)
      return
    }
    setLoading(true)
    getPublicPlaylist(token)
      .then(setPlaylist)
      .catch(() => setError('Esta playlist pública no existe o dejó de compartirse.'))
      .finally(() => setLoading(false))
  }, [token])

  async function handlePlay(item: PlaylistSongItem) {
    const trackId = `song:${item.song.id}`
    if (globalAudio) {
      if (globalAudio.track?.id === trackId) {
        if (globalAudio.isPlaying) {
          globalAudio.pause()
        } else {
          globalAudio.playTrack(globalAudio.track)
        }
        return
      }
      setLoadingPlayId(item.song.id)
      try {
        const url = item.song.play_url ?? (await getSongPlayUrl(item.song.id))
        setActiveSongId(item.song.id)
        globalAudio.playTrack({
          id: trackId,
          audioUrl: url,
          title: item.song.title ?? 'Sin título',
          coverUrl: item.song.thumbnail_url,
        })
      } catch {
        toast.info('Inicia sesión para reproducir las pistas de esta playlist')
      } finally {
        setLoadingPlayId(null)
      }
      return
    }

    if (activeSongId === item.song.id && localAudioRef.current) {
      if (localPlaying) {
        localAudioRef.current.pause()
      } else {
        void localAudioRef.current.play()
      }
      return
    }
    setLoadingPlayId(item.song.id)
    try {
      const url = item.song.play_url ?? (accessToken ? await getSongPlayUrl(item.song.id) : null)
      if (!url) {
        toast.info('Inicia sesión en MusicAI para escuchar las canciones')
        return
      }
      setActiveSongId(item.song.id)
      setLocalUrl(url)
      window.setTimeout(() => void localAudioRef.current?.play(), 50)
    } catch {
      toast.info('Inicia sesión en MusicAI para escuchar las canciones')
    } finally {
      setLoadingPlayId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-8 text-sm text-muted">
        Cargando playlist pública...
      </div>
    )
  }

  if (error || !playlist) {
    return (
      <div className="mx-auto max-w-lg px-6 py-16">
        <EmptyState
          icon={<ListMusic size={24} />}
          title="Playlist no disponible"
          description={error ?? 'No se encontró la playlist solicitada.'}
          actionLabel={accessToken ? 'Ir a mis playlists' : 'Ir al inicio'}
          actionTo={accessToken ? '/playlists' : '/'}
        />
      </div>
    )
  }

  const ordered = (playlist.playlist_songs ?? []).slice().sort((a, b) => a.position - b.position)
  const coverUrl = getPlaylistCoverUrl(playlist)
  const first = ordered[0]
  const isPlayingFirst = Boolean(
    first &&
      (globalAudio
        ? globalAudio.track?.id === `song:${first.song.id}` && globalAudio.isPlaying
        : activeSongId === first.song.id && localPlaying)
  )

  return (
    <div className="mx-auto min-h-full max-w-4xl px-6 pb-20 pt-8 text-white sm:px-8">
      <div className="mb-6 flex flex-col gap-5 sm:flex-row sm:items-center">
        <div className="flex h-32 w-32 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-card-hover text-muted">
          {coverUrl ? (
            <img src={coverUrl} alt={playlist.title} className="h-full w-full object-cover" />
          ) : (
            <ListMusic size={42} aria-hidden="true" />
          )}
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <Badge variant="primary">Playlist pública</Badge>
          <h1 className="truncate text-3xl font-bold tracking-tight">{playlist.title}</h1>
          {playlist.description && <p className="text-sm text-muted">{playlist.description}</p>}
          <p className="text-xs text-muted">
            {ordered.length} canción{ordered.length !== 1 ? 'es' : ''}
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            {first && (
              <Button
                variant="primary"
                size="sm"
                leftIcon={
                  isPlayingFirst ? (
                    <Pause size={14} fill="currentColor" />
                  ) : (
                    <Play size={14} fill="currentColor" />
                  )
                }
                onClick={() => void handlePlay(first)}
              >
                {isPlayingFirst ? 'Pausar' : 'Reproducir todo'}
              </Button>
            )}
            {!accessToken && (
              <Link to="/login" className="text-xs font-semibold text-primary hover:underline">
                Inicia sesión para escuchar completo
              </Link>
            )}
          </div>
        </div>
      </div>

      {!globalAudio && localUrl && (
        <audio
          ref={localAudioRef}
          src={localUrl}
          controls
          onPlay={() => setLocalPlaying(true)}
          onPause={() => setLocalPlaying(false)}
          onEnded={() => setLocalPlaying(false)}
          className="mb-5 w-full"
        />
      )}

      {ordered.length === 0 ? (
        <EmptyState
          icon={<ListMusic size={22} />}
          title="Playlist vacía"
          description="El creador aún no ha agregado canciones a esta playlist."
        />
      ) : (
        <div className="flex flex-col gap-1">
          {ordered.map((item, idx) => {
            const active = globalAudio
              ? globalAudio.track?.id === `song:${item.song.id}`
              : activeSongId === item.song.id
            const playing = globalAudio ? active && globalAudio.isPlaying : active && localPlaying
            return (
              <PlaylistSongRow
                key={item.id}
                item={item}
                index={idx}
                active={active}
                playing={playing}
                loading={loadingPlayId === item.song.id}
                onPlay={() => void handlePlay(item)}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
