import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Music2, Plus, Search } from 'lucide-react'

import { Button, EmptyState, Input } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { LibrarySong } from '../api/songs.api'
import AddToPlaylistModal from '../components/add-to-playlist-modal'
import LyricsView from '../components/lyrics-view'
import SongCard from '../components/song-card'
import { useLibrarySongs } from '../hooks/useLibrarySongs'

type SortOption = 'recent' | 'oldest' | 'title'

const SORT_LABELS: Record<SortOption, string> = {
  recent: 'Recientes',
  oldest: 'Antiguas',
  title: 'A–Z',
}

export default function LibraryPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<SortOption>('recent')
  const [playlistSong, setPlaylistSong] = useState<LibrarySong | null>(null)

  const {
    songs,
    loading,
    error,
    activeSong,
    showLyrics,
    setShowLyrics,
    globalTrack,
    isPlaying,
    audioRef,
    handlePlay,
    handleTogglePublic,
    handleLike,
    handleDownload,
    handleDelete,
  } = useLibrarySongs()

  const filtered = songs
    .filter((s) => {
      const q = search.toLowerCase()
      return (
        s.title?.toLowerCase().includes(q) ||
        s.description?.toLowerCase().includes(q) ||
        s.genre?.toLowerCase().includes(q)
      )
    })
    .sort((a, b) => {
      if (sort === 'recent') {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      }
      if (sort === 'oldest') {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      }
      return (a.title ?? '').localeCompare(b.title ?? '')
    })

  return (
    <div className="min-h-full px-4 pb-20 pt-6 sm:px-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Tu biblioteca</h1>
          <p className="mt-1 text-sm text-muted">Tus canciones generadas, listas para escuchar.</p>
        </div>
        <Button leftIcon={<Plus size={16} aria-hidden="true" />} onClick={() => navigate('/create')}>
          Crear canción
        </Button>
      </header>

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          {error}
        </div>
      )}

      {!loading && songs.length > 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <Search
              size={16}
              aria-hidden="true"
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
            />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar por título, género o descripción..."
              aria-label="Buscar en tu biblioteca"
              className="pl-10"
            />
          </div>

          <div className="flex gap-1 rounded-xl border border-border bg-card p-1">
            {(['recent', 'oldest', 'title'] as SortOption[]).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setSort(opt)}
                className={cn(
                  'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                  sort === opt ? 'bg-card-hover text-white' : 'text-muted hover:text-white'
                )}
              >
                {SORT_LABELS[opt]}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-[310px] animate-pulse rounded-2xl bg-card-hover" />
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((song) => (
            <SongCard
              key={song.id}
              song={song}
              onPlay={handlePlay}
              onDelete={handleDelete}
              onTogglePublic={handleTogglePublic}
              onLike={handleLike}
              onDownload={handleDownload}
              onAddToPlaylist={setPlaylistSong}
              isLiked={song.is_liked}
              likeCount={song.like_count}
              isActive={globalTrack?.id === `song:${song.id}`}
              isPlaying={globalTrack?.id === `song:${song.id}` && isPlaying}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Music2 size={24} aria-hidden="true" />}
          title={search ? 'Sin resultados' : 'Tu biblioteca está vacía'}
          description={
            search
              ? 'Prueba con otro término de búsqueda.'
              : 'Crea tu primera canción con inteligencia artificial en segundos.'
          }
          actionLabel={search ? 'Limpiar búsqueda' : 'Crear primera canción'}
          actionTo={search ? undefined : '/create'}
          onAction={search ? () => setSearch('') : undefined}
        />
      )}

      {showLyrics && activeSong && (
        <LyricsView song={activeSong} audioRef={audioRef} onClose={() => setShowLyrics(false)} />
      )}

      <AddToPlaylistModal
        song={playlistSong}
        open={Boolean(playlistSong)}
        onClose={() => setPlaylistSong(null)}
      />
    </div>
  )
}
