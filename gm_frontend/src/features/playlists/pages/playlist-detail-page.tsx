import { useEffect, useState } from 'react'
import { ArrowLeft, ListMusic } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { Button, EmptyState, useConfirm } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import type { LibrarySong } from '../../songs/api/songs.api'
import LyricsView from '../../songs/components/lyrics-view'
import {
  deletePlaylist,
  getPlaylist,
  removeSongFromPlaylist,
  sharePlaylist,
  updatePlaylist,
  type Playlist,
  type PlaylistSongItem,
} from '../api/playlists.api'
import AddSongsModal from '../components/add-songs-modal'
import PlaylistHeader from '../components/playlist-header'
import PlaylistSongRow from '../components/playlist-song-row'
import SharePlaylistModal from '../components/share-playlist-modal'
import { usePlaylistPlayback } from '../hooks/usePlaylistPlayback'

export default function PlaylistDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const confirm = useConfirm()

  const [playlist, setPlaylist] = useState<Playlist | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sharePath, setSharePath] = useState<string | null>(null)
  const [sharing, setSharing] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)

  const player = usePlaylistPlayback(playlist)

  useEffect(() => {
    if (!id) {
      return
    }
    setLoading(true)
    getPlaylist(id)
      .then(setPlaylist)
      .catch(() => setError('No se pudo cargar la playlist.'))
      .finally(() => setLoading(false))
  }, [id])

  async function handleShare() {
    if (!id) {
      return
    }
    setSharing(true)
    try {
      const { share_url: shareUrl } = await sharePlaylist(id)
      setSharePath(shareUrl)
    } catch {
      toast.error('No se pudo generar el enlace para compartir')
    } finally {
      setSharing(false)
    }
  }

  async function handleDeletePlaylist() {
    if (!id || !playlist) {
      return
    }
    const accepted = await confirm({
      title: '¿Eliminar playlist?',
      description: `Se eliminará “${playlist.title}” de forma permanente.`,
      confirmLabel: 'Eliminar playlist',
      variant: 'danger',
    })
    if (!accepted) {
      return
    }
    try {
      await deletePlaylist(id)
      toast.success('Playlist eliminada')
      navigate('/playlists')
    } catch {
      toast.error('No se pudo eliminar la playlist')
    }
  }

  async function handleRemoveSong(item: PlaylistSongItem) {
    if (!id) {
      return
    }
    const accepted = await confirm({
      title: 'Quitar canción',
      description: `¿Quieres quitar “${item.song.title ?? 'Sin título'}” de esta playlist?`,
      confirmLabel: 'Quitar de la playlist',
      variant: 'danger',
    })
    if (!accepted) {
      return
    }
    try {
      await removeSongFromPlaylist(id, item.song.id)
      player.stopIfPlaying(item.song.id)
      setPlaylist((prev) =>
        prev
          ? { ...prev, playlist_songs: prev.playlist_songs.filter((s) => s.id !== item.id) }
          : prev
      )
      toast.success('Canción quitada de la playlist')
    } catch {
      toast.error('No se pudo quitar la canción de la playlist')
    }
  }

  if (loading) {
    return <div className="px-8 py-7 text-sm text-muted">Cargando playlist...</div>
  }

  if (error || !playlist) {
    return (
      <div className="space-y-3 px-8 py-7 text-white">
        <p className="text-sm text-error">{error ?? 'Playlist no encontrada.'}</p>
        <Button variant="secondary" size="sm" onClick={() => navigate('/playlists')}>
          ← Volver a playlists
        </Button>
      </div>
    )
  }

  const orderedSongs = (playlist.playlist_songs ?? [])
    .slice()
    .sort((a, b) => a.position - b.position)
  const firstSong = orderedSongs[0]

  return (
    <div className="min-h-full px-6 pb-20 pt-7 text-white sm:px-8">
      <button
        type="button"
        onClick={() => navigate('/playlists')}
        className="mb-5 inline-flex items-center gap-1.5 text-xs font-semibold text-muted transition-colors hover:text-white"
      >
        <ArrowLeft size={14} aria-hidden="true" />
        Volver a playlists
      </button>

      <PlaylistHeader
        playlist={playlist}
        songCount={orderedSongs.length}
        isFirstPlaying={firstSong?.song.id === player.activeSongId && player.isPlaying}
        loadingPlay={player.loadingPlay}
        sharing={sharing}
        onPlayAll={() => firstSong && void player.handlePlay(firstSong)}
        onOpenAdd={() => setShowAddModal(true)}
        onShare={() => void handleShare()}
        onDelete={() => void handleDeletePlaylist()}
        onSaveDetails={async (title, description) => {
          const updated = await updatePlaylist(playlist.id, { title, description })
          setPlaylist((cur) => (cur ? { ...cur, ...updated } : updated))
          toast.success('Playlist actualizada')
        }}
      />

      {orderedSongs.length === 0 ? (
        <EmptyState
          icon={<ListMusic size={24} />}
          title="Esta playlist está vacía"
          description="Agrega canciones desde tu biblioteca para empezar a escucharla."
          actionLabel="Agregar canciones"
          onAction={() => setShowAddModal(true)}
        />
      ) : (
        <div className="flex flex-col gap-1">
          {orderedSongs.map((item, idx) => (
            <PlaylistSongRow
              key={item.id}
              item={item}
              index={idx}
              active={player.activeSongId === item.song.id}
              playing={player.activeSongId === item.song.id && player.isPlaying}
              loading={player.loadingPlay && player.activeSongId === item.song.id}
              onPlay={() => void player.handlePlay(item)}
              onRemove={() => void handleRemoveSong(item)}
            />
          ))}
        </div>
      )}

      {player.showLyrics && player.activeSong && (
        <LyricsView
          song={player.activeSong.song as unknown as LibrarySong}
          audioRef={player.audioRef}
          onClose={() => player.setShowLyrics(false)}
        />
      )}

      <AddSongsModal
        open={showAddModal}
        playlistId={playlist.id}
        existingSongIds={new Set(orderedSongs.map((s) => s.song.id))}
        onClose={() => setShowAddModal(false)}
        onAdded={async () => {
          setPlaylist(await getPlaylist(playlist.id))
          toast.success('Canciones agregadas')
        }}
      />

      <SharePlaylistModal
        open={Boolean(sharePath)}
        sharePath={sharePath}
        onClose={() => setSharePath(null)}
      />
    </div>
  )
}
