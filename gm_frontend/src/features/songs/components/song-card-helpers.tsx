import { useEffect, useState } from 'react'
import {
  AudioWaveform,
  Globe,
  ListPlus,
  Lock,
  Mic2,
  SlidersHorizontal,
  Trash2,
} from 'lucide-react'

import type { DropdownMenuItem } from '../../../components/ui'
import { getSongThumbnailUrl, type LibrarySong } from '../api/songs.api'

export function formatSongDuration(seconds?: number): string {
  if (!seconds) {
    return '—'
  }
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, '0')}`
}

export function formatSongDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function useSongCover(song: LibrarySong) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(song.thumbnail_url ?? null)
  const [coverLoading, setCoverLoading] = useState(
    !song.thumbnail_url && Boolean(song.thumbnail_s3_key)
  )

  useEffect(() => {
    if (song.thumbnail_url) {
      setThumbnailUrl(song.thumbnail_url)
      setCoverLoading(false)
      return
    }
    if (!song.thumbnail_s3_key) {
      setThumbnailUrl(null)
      setCoverLoading(false)
      return
    }
    let cancelled = false
    setCoverLoading(true)
    getSongThumbnailUrl(song.id)
      .then((url) => {
        if (!cancelled) {
          setThumbnailUrl(url)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setThumbnailUrl(null)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCoverLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [song.id, song.thumbnail_url, song.thumbnail_s3_key])

  return { thumbnailUrl, setThumbnailUrl, coverLoading }
}

interface BuildMenuArgs {
  song: LibrarySong
  showBridgeActions: boolean
  onPlaylist: () => void
  onTogglePublic?: (id: string, isPublic: boolean) => void
  onDelete?: () => void
}

export function buildSongMenuItems({
  song,
  showBridgeActions,
  onPlaylist,
  onTogglePublic,
  onDelete,
}: BuildMenuArgs): DropdownMenuItem[] {
  return [
    ...(showBridgeActions
      ? [
          {
            id: 'karaoke',
            label: 'Enviar a Karaoke',
            icon: <Mic2 size={15} />,
            to: `/karaoke/generate/${song.id}`,
          },
          {
            id: 'stems',
            label: 'Separar pistas',
            icon: <AudioWaveform size={15} />,
            to: `/stems?songId=${song.id}`,
          },
          {
            id: 'playlist',
            label: 'Agregar a Playlist',
            icon: <ListPlus size={15} />,
            onClick: onPlaylist,
          },
          {
            id: 'mix',
            label: 'Abrir en Mix DJ',
            icon: <SlidersHorizontal size={15} />,
            to: `/mix?songId=${song.id}`,
          },
        ]
      : []),
    ...(onTogglePublic
      ? [
          {
            id: 'public',
            label: song.is_public ? 'Hacer privada' : 'Publicar en comunidad',
            icon: song.is_public ? <Lock size={15} /> : <Globe size={15} />,
            onClick: () => onTogglePublic(song.id, !song.is_public),
            dividerBefore: showBridgeActions,
          },
        ]
      : []),
    ...(onDelete
      ? [
          {
            id: 'delete',
            label: 'Eliminar',
            icon: <Trash2 size={15} />,
            variant: 'danger' as const,
            onClick: onDelete,
            dividerBefore: true,
          },
        ]
      : []),
  ]
}
