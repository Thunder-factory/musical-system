import { useState } from 'react'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { toast } from '../../../store/toast.store'
import { getSongPlayUrl } from '../../songs/api/songs.api'
import type { Playlist, PlaylistSongItem } from '../api/playlists.api'

export function usePlaylistPlayback(playlist: Playlist | null) {
  const [activeSongId, setActiveSongId] = useState<string | null>(null)
  const [loadingPlay, setLoadingPlay] = useState(false)
  const [playUrls, setPlayUrls] = useState<Record<string, string>>({})
  const [showLyrics, setShowLyrics] = useState(false)
  const [activeSong, setActiveSong] = useState<PlaylistSongItem | null>(null)

  const { track, isPlaying, playTrack, pause, updateTrack, close, audioRef } =
    useGlobalAudioPlayer()

  async function handlePlay(item: PlaylistSongItem) {
    const trackId = `song:${item.song.id}`
    if (track?.id === trackId) {
      if (isPlaying) {
        pause()
      } else {
        playTrack(track)
      }
      return
    }
    setShowLyrics(false)
    setLoadingPlay(true)
    setActiveSongId(item.song.id)
    setActiveSong(item)
    try {
      const url = playUrls[item.song.id] ?? (await getSongPlayUrl(item.song.id))
      setPlayUrls((cur) => ({ ...cur, [item.song.id]: url }))
      playTrack({
        id: trackId,
        audioUrl: url,
        title: item.song.title ?? 'Sin título',
        subtitle: item.song.genre ?? undefined,
        coverUrl: item.song.thumbnail_url,
        showLyrics: false,
        onToggleLyrics: () => {
          setShowLyrics((v) => {
            updateTrack({ showLyrics: !v })
            return !v
          })
        },
        onEnded: () => {
          const ordered = (playlist?.playlist_songs ?? [])
            .slice()
            .sort((a, b) => a.position - b.position)
          const idx = ordered.findIndex((s) => s.song.id === item.song.id)
          if (ordered[idx + 1]) {
            void handlePlay(ordered[idx + 1])
          }
        },
        onClose: () => {
          setActiveSongId(null)
          setActiveSong(null)
          setShowLyrics(false)
        },
      })
    } catch {
      setActiveSongId(null)
      setActiveSong(null)
      toast.error('No se pudo reproducir la canción')
    } finally {
      setLoadingPlay(false)
    }
  }

  function stopIfPlaying(songId: string) {
    if (activeSongId === songId) {
      close()
      setActiveSongId(null)
      setActiveSong(null)
    }
  }

  return {
    activeSongId,
    activeSong,
    isPlaying,
    loadingPlay,
    showLyrics,
    setShowLyrics,
    audioRef,
    handlePlay,
    stopIfPlaying,
  }
}
