import { useEffect, useRef, useState } from 'react'
import { Heart, LoaderCircle, Pause, Play } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  getCommunityFeed,
  getCommunityStats,
  toggleLike,
  recordPlay,
} from '../../api/modules/community.api'
import type { CommunitySong, CommunityStats } from '../../api/modules/community.api'
import { getSongPlayUrl, getSongThumbnailUrl } from '../../api/modules/songs.api'
import LyricsView from '../../components/song/lyrics-view'
import MiniAudioPlayer from '../../components/player/mini-audio-player'
import { ConfigurationSelect } from '../../components/create/style-selectors-preview'

const TAGS = ['Todos', 'Trending', 'reggaeton', 'lofi', 'techno', 'pop', 'rock', 'electronic']
const GENRE_OPTIONS = TAGS.map((tag) => ({
  value: tag,
  label: tag === 'Todos' ? 'Todos los géneros' : tag === 'Trending' ? 'Trending' : tag,
}))

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) {
    return 'Ahora'
  }
  if (minutes < 60) {
    return `Hace ${minutes}m`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `Hace ${hours}h`
  }
  const days = Math.floor(hours / 24)
  return `Hace ${days}d`
}

function SongCoverImage({ song, size = 240 }: { song: CommunitySong; size?: number }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!song.thumbnail_s3_key) {
      return
    }
    getSongThumbnailUrl(song.id)
      .then(setUrl)
      .catch(() => {})
  }, [song.id, song.thumbnail_s3_key])

  if (!url) {
    return (
      <div
        style={{
          width: '100%',
          height: size,
          background: 'var(--gradient-primary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-primary)',
          opacity: 0.6,
        }}
      >
        <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
        </svg>
      </div>
    )
  }

  return (
    <img src={url} alt={song.title} style={{ width: '100%', height: size, objectFit: 'cover' }} />
  )
}

function SongCard({
  song: initial,
  onPlay,
  isActive,
  isPlaying,
  isLoading,
}: {
  song: CommunitySong
  onPlay: (song: CommunitySong) => void
  isActive: boolean
  isPlaying: boolean
  isLoading: boolean
}) {
  const [song, setSong] = useState(initial)

  async function handleLike() {
    try {
      const result = await toggleLike(song.id)
      setSong((prev) => ({ ...prev, is_liked: result.liked, like_count: result.like_count }))
    } catch {
      /* silencioso */
    }
  }

  const initials = song.user_name
    ? song.user_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : '?'

  const primaryTag = song.tags[0]

  return (
    <article className="bg-card border border-card-hover rounded-3xl overflow-hidden hover:border-primary transition-all duration-200">
      {/* Cover */}
      <div className="relative overflow-hidden" style={{ height: 240 }}>
        <SongCoverImage song={song} size={240} />
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to top, var(--bg-base) 0%, color-mix(in srgb, var(--bg-base) 55%, transparent) 18%, transparent 42%)',
          }}
        />

        {song.tags.length > 0 && (
          <div
            className="absolute top-4 left-4 px-3 py-1 rounded-full text-xs font-bold"
            style={{ background: 'var(--gradient-primary)' }}
          >
            {primaryTag?.name}
          </div>
        )}

        <button
          type="button"
          onClick={() => {
            recordPlay(song.id, 0).catch(() => {})
            onPlay(song)
          }}
          className="absolute bottom-4 right-4 w-14 h-14 rounded-full bg-primary text-black flex items-center justify-center hover:scale-105 transition-all"
        >
          {isLoading ? (
            <LoaderCircle size={22} className="animate-spin" aria-hidden="true" />
          ) : isActive && isPlaying ? (
            <Pause size={22} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={22} fill="currentColor" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Content */}
      <div className="p-5">
        {/* User info */}
        <div className="flex items-center gap-2.5 mb-3">
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
            style={{ background: 'var(--gradient-primary)' }}
          >
            {initials}
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-sm">{song.user_name}</span>
            <span className="text-xs text-muted">{timeAgo(song.created_at)}</span>
          </div>
        </div>

        {/* Song info */}
        <div className="mb-3">
          <h2 className="text-xl font-black tracking-tight">{song.title}</h2>
          {song.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {song.tags.slice(0, 2).map((t) => (
                <span
                  key={t.id}
                  className="text-xs text-primary-light px-2.5 py-1 rounded-full"
                  style={{ background: 'var(--color-primary-soft)' }}
                >
                  {t.name}
                </span>
              ))}
              {song.tags.length > 2 && (
                <span className="text-xs text-muted px-2 py-1">+{song.tags.length - 2}</span>
              )}
            </div>
          )}
          {song.description && (
            <p className="text-sm text-muted mt-3 leading-relaxed line-clamp-2">
              {song.description}
            </p>
          )}
        </div>

        {/* Stats */}
        <div className="flex items-center justify-between border-t border-card-hover pt-3 text-xs text-muted">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={handleLike}
              className="flex items-center gap-1.5 transition-colors"
              style={{ color: song.is_liked ? 'var(--color-error)' : undefined }}
            >
              <Heart size={15} fill={song.is_liked ? 'currentColor' : 'none'} aria-hidden="true" />
              {song.like_count.toLocaleString()}
            </button>
            <div className="flex items-center gap-1.5">
              <Play size={13} fill="currentColor" aria-hidden="true" />
              {song.play_count.toLocaleString()}
            </div>
          </div>
          <span>{timeAgo(song.created_at)}</span>
        </div>
      </div>
    </article>
  )
}

export default function CommunityPage() {
  const navigate = useNavigate()
  const [songs, setSongs] = useState<CommunitySong[]>([])
  const [stats, setStats] = useState<CommunityStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setMore] = useState(false)
  const [page, setPage] = useState(1)
  const [hasNext, setHasNext] = useState(false)
  const [search, setSearch] = useState('')
  const [activeTag, setActiveTag] = useState('Todos')
  const [publishing] = useState(false)

  const [activeSong, setActiveSong] = useState<CommunitySong | null>(null)
  const [activeUrl, setActiveUrl] = useState<string | null>(null)
  const [loadingPlay, setLoadingPlay] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [showLyrics, setShowLyrics] = useState(false)
  const audioRef = useRef<HTMLAudioElement>(null)

  async function handlePlay(song: CommunitySong) {
    if (activeSong?.id === song.id && activeUrl && audioRef.current) {
      if (audioRef.current.paused) {
        await audioRef.current.play().catch(() => {})
      } else {
        audioRef.current.pause()
      }
      return
    }
    setShowLyrics(false)
    setLoadingPlay(true)
    setIsPlaying(false)
    audioRef.current?.pause()
    setActiveUrl(null)
    setActiveSong(song)
    try {
      const url = await getSongPlayUrl(song.id)
      setActiveUrl(url)
    } catch {
      setActiveUrl(null)
      setActiveSong(null)
      setIsPlaying(false)
    } finally {
      setLoadingPlay(false)
    }
  }

  function loadFeed(p: number, tag: string, q: string, append = false) {
    if (p === 1) {
      setLoading(true)
    } else {
      setMore(true)
    }

    const tagParam = tag === 'Todos' || tag === 'Trending' ? '' : tag
    getCommunityFeed({ search: q, tag: tagParam, page: p })
      .then((res) => {
        setSongs((prev) => (append ? [...prev, ...res.results] : res.results))
        setHasNext(res.has_next)
        setPage(p)
      })
      .finally(() => {
        setLoading(false)
        setMore(false)
      })
  }

  useEffect(() => {
    loadFeed(1, activeTag, search)
  }, [])
  useEffect(() => {
    getCommunityStats()
      .then(setStats)
      .catch(() => {})
  }, [])

  function handleTagChange(tag: string) {
    setActiveTag(tag)
    loadFeed(1, tag, search)
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    loadFeed(1, activeTag, search)
  }

  function handlePublishSong() {
    navigate('/library')
  }

  return (
    <div className="min-h-full px-8 pt-7 pb-20 text-white">
      {/* Header */}
      <div className="flex flex-col gap-6 mb-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-[32px] font-bold tracking-tight">Comunidad</h1>
            <p className="text-sm text-muted mt-1">
              Explora y escucha creaciones de otros usuarios.
            </p>
          </div>
          <button
            onClick={handlePublishSong}
            disabled={publishing}
            className="px-5 py-2.5 rounded-full text-sm font-bold transition-all duration-200 hover:scale-[1.02]"
            style={{ background: 'var(--gradient-primary)' }}
          >
            + Publicar canción
          </button>
        </div>

        {/* Search + genre filter */}
        <div className="flex flex-col lg:flex-row gap-4 lg:items-center">
          <form onSubmit={handleSearch} className="relative w-full lg:flex-1">
            <input
              type="text"
              placeholder="Buscar canciones o creadores..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-card border border-card-hover focus:border-primary outline-none rounded-xl px-4 py-3 text-sm transition-all"
            />
            <button
              type="submit"
              style={{
                position: 'absolute',
                right: 12,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--text-placeholder)',
              }}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor">
                <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16a6.471 6.471 0 004.23-1.57l.27.28v.79L20 21.5 21.5 20l-6-6zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
              </svg>
            </button>
          </form>

          <div className="w-full lg:w-64 lg:flex-none">
            <ConfigurationSelect
              label="Filtrar por género"
              value={activeTag}
              options={GENRE_OPTIONS}
              onChange={handleTagChange}
              showLabel={false}
            />
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {[
          { label: 'Canciones publicadas', value: stats?.public_songs?.toLocaleString() ?? '…' },
          { label: 'Usuarios activos', value: stats?.active_users?.toLocaleString() ?? '…' },
          {
            label: 'Reproducciones hoy',
            value: stats
              ? stats.plays_today >= 1000
                ? `${(stats.plays_today / 1000).toFixed(1)}K`
                : stats.plays_today.toString()
              : '…',
          },
        ].map(({ label, value }) => (
          <div key={label} className="bg-card border border-card-hover rounded-2xl p-5">
            <span className="text-muted text-sm">{label}</span>
            <h3 className="text-3xl font-black mt-2">{value}</h3>
          </div>
        ))}
      </div>

      {/* Feed */}
      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              style={{
                height: 420,
                borderRadius: 24,
                background: 'var(--gradient-skeleton)',
                backgroundSize: '200% 100%',
                animation: 'shimmer 1.5s infinite',
              }}
            />
          ))}
          <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
        </div>
      ) : songs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <h3 className="text-2xl font-bold mb-2">No se encontraron canciones</h3>
          <p className="text-muted text-sm">
            Prueba con otro término o filtro, o sé el primero en publicar.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
            {songs.map((song) => (
              <SongCard
                key={song.id}
                song={song}
                onPlay={handlePlay}
                isActive={activeSong?.id === song.id}
                isPlaying={activeSong?.id === song.id && isPlaying}
                isLoading={activeSong?.id === song.id && loadingPlay}
              />
            ))}
          </div>

          {hasNext && (
            <div className="flex justify-center mt-8">
              <button
                onClick={() => loadFeed(page + 1, activeTag, search, true)}
                disabled={loadingMore}
                className="px-8 py-3 rounded-full text-sm font-semibold transition-all"
                style={{
                  background: 'var(--bg-card-hover)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-base)',
                  opacity: loadingMore ? 0.6 : 1,
                }}
              >
                {loadingMore ? 'Cargando...' : 'Ver más'}
              </button>
            </div>
          )}
        </>
      )}

      {/* Mini-player */}
      {activeSong && (
        <MiniAudioPlayer
          audioRef={audioRef}
          audioUrl={activeUrl}
          title={activeSong.title}
          subtitle={activeSong.tags[0]?.name}
          loading={loadingPlay}
          showLyrics={showLyrics}
          onToggleLyrics={() => setShowLyrics((value) => !value)}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
        />
      )}

      {/* Lyrics overlay */}
      {showLyrics && activeSong && (
        <LyricsView
          song={activeSong as any}
          audioRef={audioRef}
          onClose={() => setShowLyrics(false)}
        />
      )}
    </div>
  )
}
