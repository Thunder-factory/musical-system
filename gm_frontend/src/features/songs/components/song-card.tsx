import { useState } from 'react'
import { Download, Globe, Lock, MoreHorizontal } from 'lucide-react'

import { DropdownMenu, useConfirm } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { toast } from '../../../store/toast.store'
import { toggleSongLike } from '../api/songs.api'
import type { LibrarySong, SongTag } from '../api/songs.api'
import AddToPlaylistModal from './add-to-playlist-modal'
import { SongCardCover } from './song-card-cover'
import { buildSongMenuItems, formatSongDate, formatSongDuration } from './song-card-helpers'

export interface SongCardProps {
  song: LibrarySong
  onPlay: (song: LibrarySong) => void
  onDelete?: (id: string) => void
  onTogglePublic?: (id: string, isPublic: boolean) => void
  onPublish?: (id: string, isPublic: boolean) => void
  onLike?: (id: string) => void | Promise<void>
  onDownload?: (id: string) => void
  onAddToPlaylist?: (song: LibrarySong) => void
  isLiked?: boolean
  likeCount?: number
  showBridgeActions?: boolean
  isActive?: boolean
  isPlaying?: boolean
  isLoading?: boolean
}

export function SongCard({
  song,
  onPlay,
  onDelete,
  onTogglePublic,
  onPublish,
  onLike,
  onDownload,
  onAddToPlaylist,
  isLiked,
  likeCount,
  showBridgeActions = true,
  isActive = false,
  isPlaying = false,
  isLoading = false,
}: SongCardProps) {
  const confirm = useConfirm()
  const [localLiked, setLocalLiked] = useState(Boolean(song.is_liked))
  const [localLikes, setLocalLikes] = useState(song.like_count ?? 0)
  const [liking, setLiking] = useState(false)
  const [playlistOpen, setPlaylistOpen] = useState(false)

  const liked = isLiked ?? localLiked
  const likes = likeCount ?? localLikes
  const publicHandler = onTogglePublic ?? onPublish

  async function handleLike() {
    if (liking) {
      return
    }
    if (onLike) {
      await onLike(song.id)
      return
    }
    setLiking(true)
    try {
      const result = await toggleSongLike(song.id)
      setLocalLiked(result.liked)
      setLocalLikes(result.like_count)
    } catch {
      toast.error('No se pudo actualizar el me gusta')
    } finally {
      setLiking(false)
    }
  }

  async function handleDelete() {
    if (!onDelete) {
      return
    }
    const ok = await confirm({
      title: 'Eliminar canción',
      description: `¿Seguro que deseas eliminar "${song.title || 'esta canción'}"? Esta acción no se puede deshacer.`,
      confirmLabel: 'Eliminar',
      variant: 'danger',
    })
    if (ok) {
      onDelete(song.id)
    }
  }

  const tags: string[] =
    song.tags && song.tags.length > 0
      ? song.tags.map((t: SongTag) => t.name)
      : ([song.genre, song.mood].filter(Boolean) as string[])

  const menuItems = buildSongMenuItems({
    song,
    showBridgeActions,
    onPlaylist: () => (onAddToPlaylist ? onAddToPlaylist(song) : setPlaylistOpen(true)),
    onTogglePublic: publicHandler,
    onDelete: onDelete ? () => void handleDelete() : undefined,
  })

  return (
    <>
      <article
        className={cn(
          'group relative flex flex-col rounded-2xl border bg-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[var(--shadow)]',
          isActive ? 'border-primary' : 'border-border hover:border-border-strong'
        )}
      >
        <SongCardCover
          song={song}
          tags={tags}
          liked={liked}
          likes={likes}
          liking={liking}
          isPlaying={isPlaying}
          isLoading={isLoading}
          onPlay={() => onPlay(song)}
          onLike={() => void handleLike()}
        />

        <div className="flex flex-1 flex-col justify-between gap-3 p-3.5">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted">
              <span>{formatSongDate(song.created_at)}</span>
              <span className="rounded-full bg-card-hover px-2.5 py-0.5 tabular-nums">
                {formatSongDuration(song.audio_duration)}
              </span>
            </div>
            {song.description && (
              <p className="line-clamp-2 text-xs leading-relaxed text-muted">{song.description}</p>
            )}
          </div>

          <div className="flex items-center gap-1 border-t border-border pt-2.5">
            {onDownload && (
              <button
                type="button"
                onClick={() => onDownload(song.id)}
                aria-label={`Descargar ${song.title}`}
                title="Descargar"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-card-hover hover:text-white"
              >
                <Download size={15} aria-hidden="true" />
              </button>
            )}
            {publicHandler && (
              <button
                type="button"
                onClick={() => publicHandler(song.id, !song.is_public)}
                className={cn(
                  'inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium transition-colors',
                  song.is_public
                    ? 'bg-success-soft text-success hover:bg-success/15'
                    : 'text-muted hover:bg-card-hover hover:text-white'
                )}
              >
                {song.is_public ? (
                  <Globe size={14} aria-hidden="true" />
                ) : (
                  <Lock size={14} aria-hidden="true" />
                )}
                <span>{song.is_public ? 'Pública' : 'Publicar'}</span>
              </button>
            )}
            {menuItems.length > 0 && (
              <div className="ml-auto">
                <DropdownMenu
                  align="right"
                  triggerAriaLabel={`Más acciones para ${song.title || 'canción'}`}
                  triggerClassName="h-8 w-8 text-muted hover:bg-card-hover hover:text-white"
                  trigger={<MoreHorizontal size={16} aria-hidden="true" />}
                  items={menuItems}
                />
              </div>
            )}
          </div>
        </div>
      </article>

      {!onAddToPlaylist && playlistOpen && (
        <AddToPlaylistModal song={song} open={playlistOpen} onClose={() => setPlaylistOpen(false)} />
      )}
    </>
  )
}

export default SongCard
