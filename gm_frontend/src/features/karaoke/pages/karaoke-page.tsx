import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Input } from '../../../components/ui'
import { isFirebaseConfigured } from '../../../lib/env'
import { toast } from '../../../store/toast.store'
import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import type { KaraokeCatalogSong, MyKaraokeItem } from '../../../types'
import { getSongPlayUrl, type UploadSongResponse } from '../../songs/api/songs.api'
import { getKaraokeCatalog, getMyKaraokes } from '../api/karaoke.api'
import JoinRoomModal from '../components/join-room-modal'
import KaraokeCatalogList from '../components/karaoke-catalog-list'
import KaraokeHeader from '../components/karaoke-header'
import UploadSongModal from '../components/upload-song-modal'

type Source = 'library' | 'community' | 'my-karaokes'

const TABS: Array<{ id: Source; label: string }> = [
  { id: 'library', label: 'Mi Biblioteca' },
  { id: 'community', label: 'Comunidad' },
  { id: 'my-karaokes', label: 'Mis Karaokes' },
]

export default function KaraokePage() {
  const navigate = useNavigate()
  const firebaseReady = isFirebaseConfigured()
  const [source, setSource] = useState<Source>('library')
  const [songs, setSongs] = useState<KaraokeCatalogSong[]>([])
  const [myKaraokes, setMyKaraokes] = useState<MyKaraokeItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showJoinModal, setShowJoinModal] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)

  const { track: globalTrack, isPlaying, playTrack, pause } = useGlobalAudioPlayer()

  useEffect(() => {
    setLoading(true)
    setError(null)
    setSongs([])
    setMyKaraokes([])

    if (source === 'my-karaokes') {
      getMyKaraokes()
        .then(setMyKaraokes)
        .catch(() => setError('No se pudieron cargar tus karaokes. Inténtalo de nuevo.'))
        .finally(() => setLoading(false))
    } else {
      getKaraokeCatalog(source)
        .then(setSongs)
        .catch(() => setError('No se pudieron cargar las canciones. Inténtalo de nuevo.'))
        .finally(() => setLoading(false))
    }
  }, [source])

  async function handleTogglePreview(song: KaraokeCatalogSong) {
    const previewTrackId = `karaoke-preview:${song.id}`
    if (globalTrack?.id === previewTrackId) {
      if (isPlaying) {
        pause()
      } else if (globalTrack.audioUrl) {
        playTrack(globalTrack)
      }
      return
    }
    try {
      const url = await getSongPlayUrl(song.id)
      playTrack({
        id: previewTrackId,
        audioUrl: url,
        title: song.title,
        subtitle: song.user_name ? `por ${song.user_name}` : 'Vista previa',
        coverUrl: song.thumbnail_url,
      })
    } catch {
      toast.error('No se pudo reproducir la vista previa')
    }
  }

  function handleSelect(song: KaraokeCatalogSong) {
    navigate(`/karaoke/generate/${song.id}`, {
      state: { songTitle: song.title, source, thumbnailUrl: song.thumbnail_url },
    })
  }

  function handlePlayKaraoke(item: MyKaraokeItem) {
    navigate(`/karaoke/play/${item.karaoke_id}`, {
      state: { songId: item.song_id, songTitle: item.song_title, source: 'my-karaokes' },
    })
  }

  function handleUploaded(song: UploadSongResponse) {
    const catalogSong: KaraokeCatalogSong = {
      id: song.id,
      title: song.title,
      thumbnail_url: song.thumbnail_url,
      source: 'library',
      tags: song.tags?.map((tag) => tag.name) ?? [],
    }
    setSongs((current) => [catalogSong, ...current.filter((item) => item.id !== catalogSong.id)])
    setSource('library')
    setShowUploadModal(false)
  }

  const query = search.trim().toLowerCase()
  const filteredSongs = query ? songs.filter((s) => s.title.toLowerCase().includes(query)) : songs
  const filteredMyKaraokes = query
    ? myKaraokes.filter((k) => k.song_title.toLowerCase().includes(query))
    : myKaraokes

  return (
    <div className="min-h-full px-6 pb-20 pt-7 text-white sm:px-8">
      <KaraokeHeader
        showUpload={source === 'library'}
        firebaseReady={firebaseReady}
        onOpenUpload={() => setShowUploadModal(true)}
        onOpenJoin={() => setShowJoinModal(true)}
      />

      {!firebaseReady && (
        <p className="mb-5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-2.5 text-xs text-warning">
          Las salas compartidas en vivo están en preparación. Mientras tanto puedes generar y cantar
          cualquier pista en modo individual.
        </p>
      )}

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div className="flex gap-1 rounded-full bg-card-hover p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSource(t.id)}
              className={`whitespace-nowrap rounded-full px-4 py-1.5 text-xs font-semibold transition-colors sm:text-sm ${
                source === t.id ? 'bg-surface text-white shadow' : 'text-muted hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="relative min-w-[220px] flex-1">
          <Search
            size={16}
            aria-hidden="true"
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
          />
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar canción..."
            aria-label="Buscar canción"
            className="pl-10"
          />
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-72 animate-pulse rounded-xl bg-card-hover" />
          ))}
        </div>
      ) : (
        !error && (
          <KaraokeCatalogList
            source={source}
            songs={filteredSongs}
            myKaraokes={filteredMyKaraokes}
            search={search}
            activeTrackId={globalTrack?.id}
            isPlaying={isPlaying}
            onSelectSong={handleSelect}
            onTogglePreview={handleTogglePreview}
            onPlayMyKaraoke={handlePlayKaraoke}
            onOpenUpload={() => setShowUploadModal(true)}
            onClearSearch={() => setSearch('')}
          />
        )
      )}

      <JoinRoomModal open={showJoinModal} onClose={() => setShowJoinModal(false)} />
      <UploadSongModal
        open={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onUploaded={handleUploaded}
      />
    </div>
  )
}
