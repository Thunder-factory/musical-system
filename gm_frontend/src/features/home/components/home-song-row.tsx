import { Sparkles, TrendingUp } from 'lucide-react'

import { EmptyState } from '../../../components/ui'
import HomeSongCard, { type HomeSong } from '../../songs/components/home-song-card'

export type HomeRowState = { songs: HomeSong[]; loading: boolean; error: boolean }

interface HomeSongRowProps {
  row: HomeRowState
  emptyTitle: string
  emptyDescription: string
  emptyActionLabel: string
  emptyActionTo: string
  activeId?: string
  isPlaying: boolean
  loadingId: string | null
  onPlay: (song: HomeSong) => void
}

export default function HomeSongRow({
  row,
  emptyTitle,
  emptyDescription,
  emptyActionLabel,
  emptyActionTo,
  activeId,
  isPlaying,
  loadingId,
  onPlay,
}: HomeSongRowProps) {
  if (row.loading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-[280px] w-[200px] shrink-0 animate-pulse rounded-2xl bg-card-hover" />
        ))}
      </div>
    )
  }

  if (row.error) {
    return (
      <EmptyState
        icon={<TrendingUp size={20} aria-hidden="true" />}
        title="No se pudieron cargar las canciones"
        description="Ocurrió un problema de conexión. Intenta de nuevo en unos instantes."
        actionLabel="Crear canción"
        actionTo="/create"
      />
    )
  }

  if (row.songs.length === 0) {
    return (
      <EmptyState
        icon={<Sparkles size={20} aria-hidden="true" />}
        title={emptyTitle}
        description={emptyDescription}
        actionLabel={emptyActionLabel}
        actionTo={emptyActionTo}
      />
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
