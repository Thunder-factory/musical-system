// ─────────────────────────────────────────────────────────────────────────────
// src/pages/library/library-page.tsx
// Biblioteca del usuario. Consume /api/songs/library/ y renderiza SongCards.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useState } from 'react'
import {
  deleteSong,
  getLibrary,
  getSongPlayUrl,
  toggleSongPublic,
} from '../../api/modules/songs.api'
import type { LibrarySong } from '../../api/modules/songs.api'
import SongCard from '../../components/song/song-card'
import LyricsView from '../../components/song/lyrics-view'
import { useGlobalAudioPlayer } from '../../components/player/use-global-audio-player'
import styles from './library-page.module.css'
import { useNavigate } from 'react-router-dom'

type SortOption = 'recent' | 'oldest' | 'title'

export default function LibraryPage() {
  const [songs, setSongs] = useState<LibrarySong[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<SortOption>('recent')

  // ── Audio player state ─────────────────────────────────────
  const [activeSong, setActiveSong] = useState<LibrarySong | null>(null)
  const [showLyrics, setShowLyrics] = useState(false)
  const {
    track: globalTrack,
    isPlaying,
    playTrack,
    pause,
    updateTrack,
    audioRef,
  } = useGlobalAudioPlayer()

  const navigate = useNavigate()

  // ── Fetch library ──────────────────────────────────────────
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getLibrary()
      .then((data) => {
        if (cancelled) {
          return
        }

        setSongs(data)
        data
          .filter((song) => !song.play_url)
          .forEach((song) => {
            getSongPlayUrl(song.id)
              .then((url) => {
                if (!cancelled) {
                  setSongs((current) =>
                    current.map((item) => (item.id === song.id ? { ...item, play_url: url } : item))
                  )
                }
              })
              .catch(() => {
                // La URL se solicitará nuevamente al pulsar reproducir.
              })
          })
      })
      .catch(() => setError('No se pudo cargar tu biblioteca. Intenta de nuevo.'))
      .finally(() => setLoading(false))

    return () => {
      cancelled = true
    }
  }, [])

  // ── Play handler ───────────────────────────────────────────
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
        title: song.title ?? 'Sin título',
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
    }
  }

  // ── Publish handler ────────────────────────────────────────
  async function handlePublish(songId: string, isPublic: boolean) {
    try {
      await toggleSongPublic(songId, isPublic)
      setSongs((prev) => prev.map((s) => (s.id === songId ? { ...s, is_public: isPublic } : s)))
    } catch {
      alert('No se pudo publicar. Intenta de nuevo.')
    }
  }

  // ── Download handler ──────────────────────────────────────
  async function handleDownload(songId: string) {
    try {
      const song = songs.find((s) => s.id === songId)
      const url = song?.play_url ?? (await getSongPlayUrl(songId))
      const a = document.createElement('a')
      a.href = url
      a.download = `${song?.title ?? 'cancion'}.mp3`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } catch {
      alert('No se pudo descargar la canción. Intenta de nuevo.')
    }
  }

  // ── Delete handler ─────────────────────────────────────────
  async function handleDelete(songId: string) {
    try {
      await deleteSong(songId)
      setSongs((prev) => prev.filter((s) => s.id !== songId))
      if (activeSong?.id === songId) {
        pause()
        setActiveSong(null)
        setShowLyrics(false)
      }
    } catch {
      alert('No se pudo eliminar la canción. Intenta de nuevo.')
    }
  }

  // ── Derived list ───────────────────────────────────────────
  const filtered = songs
    .filter(
      (s) =>
        s.title?.toLowerCase().includes(search.toLowerCase()) ||
        s.description?.toLowerCase().includes(search.toLowerCase()) ||
        s.genre?.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      if (sort === 'recent') {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      }
      if (sort === 'oldest') {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      }
      if (sort === 'title') {
        return (a.title ?? '').localeCompare(b.title ?? '')
      }
      return 0
    })

  // ── Skeletons ──────────────────────────────────────────────
  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.pageTitle}>Tu biblioteca</h1>
            <p className={styles.pageSubtitle}>Cargando tus canciones...</p>
          </div>
        </div>
        <div className={styles.grid}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={styles.skeleton} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.pageTitle}>Tu biblioteca</h1>
          <p className={styles.pageSubtitle}>Tus canciones generadas, listas para escuchar.</p>
        </div>
        <button
          onClick={() => navigate('/create')}
          className="px-5 py-2.5 rounded-full text-sm font-bold transition-all duration-200 hover:scale-[1.02]"
          style={{ background: 'var(--gradient-primary)' }}
        >
          + Crear canción
        </button>
      </div>

      {/* ── Error ──────────────────────────────────────────────── */}
      {error && (
        <div className={styles.errorBanner}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
          </svg>
          {error}
        </div>
      )}

      {/* ── Controls ───────────────────────────────────────────── */}
      {songs.length > 0 && (
        <div className={styles.controls}>
          <div className={styles.searchWrapper}>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="currentColor"
              className={styles.searchIcon}
            >
              <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16a6.471 6.471 0 004.23-1.57l.27.28v.79L20 21.5 21.5 20l-6-6zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
            </svg>
            <input
              type="text"
              placeholder="Buscar en tu biblioteca..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={styles.searchInput}
            />
          </div>

          <div className={styles.sortGroup}>
            {(['recent', 'oldest', 'title'] as SortOption[]).map((opt) => (
              <button
                key={opt}
                onClick={() => setSort(opt)}
                className={`${styles.sortBtn} ${sort === opt ? styles.sortBtnActive : ''}`}
              >
                {{ recent: 'Recientes', oldest: 'Antiguas', title: 'A–Z' }[opt]}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Grid ───────────────────────────────────────────────── */}
      {filtered.length > 0 ? (
        <div className={styles.grid}>
          {filtered.map((song) => (
            <SongCard
              key={song.id}
              song={song}
              onPlay={handlePlay}
              onDelete={handleDelete}
              onPublish={handlePublish}
              onDownload={handleDownload}
              isActive={globalTrack?.id === `song:${song.id}`}
              isPlaying={globalTrack?.id === `song:${song.id}` && isPlaying}
            />
          ))}
        </div>
      ) : (
        !loading && (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
              </svg>
            </div>
            <h3 className={styles.emptyTitle}>
              {search ? 'Sin resultados' : 'Tu biblioteca está vacía'}
            </h3>
            <p className={styles.emptyText}>
              {search
                ? 'Prueba con otro término de búsqueda.'
                : 'Genera tu primera canción en la pestaña "Crear canción".'}
            </p>
          </div>
        )
      )}

      {/* ── Vista de letra a pantalla completa ──────────────────── */}
      {showLyrics && activeSong && (
        <LyricsView song={activeSong} audioRef={audioRef} onClose={() => setShowLyrics(false)} />
      )}
    </div>
  )
}
