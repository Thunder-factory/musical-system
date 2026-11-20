import { useState } from 'react'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { toast } from '../../../store/toast.store'
import { getSongPlayUrl, getSongThumbnailUrl } from '../../songs/api/songs.api'
import type { CommunitySong } from '../api/community.api'

export function useCommunityPlayback() {
  const [loadingSongId, setLoadingSongId] = useState<string | null>(null)
  const [activeSong, setActiveSong] = useState<CommunitySong | null>(null)
  const [showLyrics, setShowLyrics] = useState(false)

  const { track: globalTrack, isPlaying, playTrack, pause, updateTrack, audioRef } =
    useGlobalAudioPlayer()

  async function handlePlay(song: CommunitySong, resolvedCoverUrl?: string) {
    const trackId = `song:${song.id}`
    if (globalTrack?.id === trackId) {
      if (isPlaying) {
        pause()
      } else {
        playTrack(globalTrack)
      }
      return
    }
    setShowLyrics(false)
    setActiveSong(song)
    setLoadingSongId(song.id)
    try {
      const [url, thumb] = await Promise.all([
        getSongPlayUrl(song.id),
        resolvedCoverUrl
          ? Promise.resolve(resolvedCoverUrl)
          : song.thumbnail_s3_key
            ? getSongThumbnailUrl(song.id).catch(() => undefined)
            : Promise.resolve(undefined),
      ])
      playTrack({
        id: trackId,
        audioUrl: url,
        title: song.title,
        subtitle: song.tags[0]?.name,
        coverUrl: thumb ?? undefined,
        showLyrics: false,
        onToggleLyrics: () => {
          setShowLyrics((value) => {
            updateTrack({ showLyrics: !value })
            return !value
          })
        },
        onClose: () => {
          setActiveSong(null)
          setShowLyrics(false)
        },
      })
    } catch {
      setActiveSong(null)
      toast.error('No se pudo reproducir la canción')
    } finally {
      setLoadingSongId(null)
    }
  }

  return {
    audioRef,
    globalTrack,
    isPlaying,
    loadingSongId,
    activeSong,
    showLyrics,
    setShowLyrics,
    handlePlay,
  }
}
