import { useEffect, useState } from 'react'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { toast } from '../../../store/toast.store'
import {
  deleteSong,
  getLibrary,
  getSongPlayUrl,
  toggleSongLike,
  toggleSongPublic,
  type LibrarySong,
} from '../api/songs.api'

export function useLibrarySongs() {
  const [songs, setSongs] = useState<LibrarySong[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeSong, setActiveSong] = useState<LibrarySong | null>(null)
  const [showLyrics, setShowLyrics] = useState(false)

  const { track: globalTrack, isPlaying, playTrack, pause, updateTrack, audioRef } =
    useGlobalAudioPlayer()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getLibrary()
      .then((data) => {
        if (!cancelled) {
          setSongs(data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('No se pudo cargar tu biblioteca. Intenta de nuevo.')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

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

    setShowLyrics(false)
    setActiveSong(song)
    try {
      const url = song.play_url ?? (await getSongPlayUrl(song.id))
      playTrack({
        id: trackId,
        audioUrl: url,
        title: song.title || 'Sin título',
        subtitle: song.genre ?? undefined,
        coverUrl: song.thumbnail_url,
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
    }
  }

  async function handleTogglePublic(songId: string, isPublic: boolean) {
    try {
      await toggleSongPublic(songId, isPublic)
      setSongs((prev) => prev.map((s) => (s.id === songId ? { ...s, is_public: isPublic } : s)))
      toast.success(isPublic ? 'Canción publicada en comunidad' : 'Canción marcada como privada')
    } catch {
      toast.error('No se pudo actualizar la visibilidad', 'Intenta de nuevo.')
    }
  }

  async function handleLike(songId: string) {
    try {
      const result = await toggleSongLike(songId)
      setSongs((prev) =>
        prev.map((s) =>
          s.id === songId ? { ...s, is_liked: result.liked, like_count: result.like_count } : s
        )
      )
    } catch {
      toast.error('No se pudo registrar tu me gusta')
    }
  }

  async function handleDownload(songId: string) {
    try {
      const song = songs.find((s) => s.id === songId)
      const url = song?.play_url ?? (await getSongPlayUrl(songId))
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${song?.title || 'cancion'}.mp3`
      anchor.target = '_blank'
      anchor.rel = 'noopener noreferrer'
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
    } catch {
      toast.error('No se pudo descargar la canción', 'Intenta de nuevo.')
    }
  }

  async function handleDelete(songId: string) {
    try {
      await deleteSong(songId)
      setSongs((prev) => prev.filter((s) => s.id !== songId))
      if (activeSong?.id === songId) {
        pause()
        setActiveSong(null)
        setShowLyrics(false)
      }
      toast.success('Canción eliminada')
    } catch {
      toast.error('No se pudo eliminar la canción', 'Intenta de nuevo.')
    }
  }

  return {
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
  }
}
