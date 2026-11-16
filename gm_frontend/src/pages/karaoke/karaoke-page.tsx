import { useEffect, useState } from 'react'
import { Pause, Play, Upload, UsersRound } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getKaraokeCatalog, getMyKaraokes } from '../../api/modules/karaoke.api'
import { getSongPlayUrl } from '../../api/modules/songs.api'
import type { UploadSongResponse } from '../../api/modules/songs.api'
import JoinRoomModal from '../../components/karaoke/join-room-modal'
import UploadSongModal from '../../components/karaoke/upload-song-modal'
import { useGlobalAudioPlayer } from '../../components/player/use-global-audio-player'
import type { KaraokeCatalogSong, MyKaraokeItem } from '../../types'
import styles from './karaoke-page.module.css'

type Source = 'library' | 'community' | 'my-karaokes'

// ── Tarjeta individual ────────────────────────────────────────────────────────

function KaraokeSongCard({
  song,
  onSelect,
  isPreviewing,
  onTogglePreview,
}: {
  song: KaraokeCatalogSong
  onSelect: (song: KaraokeCatalogSong) => void
  isPreviewing: boolean
  onTogglePreview: (song: KaraokeCatalogSong) => void
}) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null)

  useEffect(() => {
    if (song.thumbnail_url) {
      setThumbnailUrl(song.thumbnail_url)
    } else {
      setThumbnailUrl(null)
    }
  }, [song.thumbnail_url])

  const tags = song.tags?.slice(0, 3) ?? []

  return (
    <article className={styles.songCard}>
      <div className={styles.songCover}>
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={`Portada de ${song.title}`}
            className={styles.songCoverImg}
            onError={() => setThumbnailUrl(null)}
          />
        ) : (
          <div className={styles.songCoverPlaceholder}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
            </svg>
          </div>
        )}
        <div className={styles.songCoverOverlay} />

        {/* Botón reproducir (preview) sobre la portada */}
        <button
          className={`${styles.previewBtn} ${isPreviewing ? styles.previewBtnActive : ''}`}
          onClick={() => onTogglePreview(song)}
          aria-label={isPreviewing ? 'Pausar' : 'Reproducir'}
          title={isPreviewing ? 'Pausar' : 'Escuchar'}
        >
          {isPreviewing ? (
            <Pause size={18} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={18} fill="currentColor" aria-hidden="true" />
          )}
        </button>
      </div>

      <div className={styles.songInfo}>
        <p className={styles.songTitle}>{song.title}</p>
        {song.user_name && <p className={styles.songAuthor}>por {song.user_name}</p>}
      </div>

      {tags.length > 0 && (
        <div className={styles.tagRow}>
          {tags.map((tag) => (
            <span key={tag} className={styles.tagPill}>
              {tag}
            </span>
          ))}
        </div>
      )}

      <button className={styles.singBtn} onClick={() => onSelect(song)}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
        </svg>
        Karaoke
      </button>
    </article>
  )
}

// ── Tarjeta "Mis Karaokes" ────────────────────────────────────────────────────

const STATUS_LABEL: Record<MyKaraokeItem['status'], string> = {
  ready: '',
  queued: 'En cola',
  processing: 'Procesando...',
  failed: 'Error',
}

function MyKaraokeCard({
  item,
  onPlay,
}: {
  item: MyKaraokeItem
  onPlay: (item: MyKaraokeItem) => void
}) {
  const isReady = item.status === 'ready'

  return (
    <article className={styles.songCard}>
      <div className={styles.songCover}>
        {item.thumbnail_url ? (
          <img
            src={item.thumbnail_url}
            alt={`Portada de ${item.song_title}`}
            className={styles.songCoverImg}
          />
        ) : (
          <div className={styles.songCoverPlaceholder}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
            </svg>
          </div>
        )}
        <div className={styles.songCoverOverlay} />
        {!isReady && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--overlay)',
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--text-base-soft)',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
            }}
          >
            {STATUS_LABEL[item.status] || item.status}
          </div>
        )}
      </div>

      <div className={styles.songInfo}>
        <p className={styles.songTitle}>{item.song_title}</p>
      </div>

      <button
        className={styles.singBtn}
        onClick={() => onPlay(item)}
        disabled={!isReady}
        title={isReady ? 'Cantar' : STATUS_LABEL[item.status]}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
        </svg>
        Cantar
      </button>
    </article>
  )
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function KaraokePage() {
  const navigate = useNavigate()
  const [source, setSource] = useState<Source>('library')
  const [songs, setSongs] = useState<KaraokeCatalogSong[]>([])
  const [myKaraokes, setMyKaraokes] = useState<MyKaraokeItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showJoinModal, setShowJoinModal] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)

  const { track: globalTrack, isPlaying, playTrack, pause } = useGlobalAudioPlayer()

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
      // La card conserva su estado normal si no se puede preparar el audio.
    }
  }

  useEffect(() => {
    setLoading(true)
    setError(null)
    setSongs([])
    setMyKaraokes([])
    if (source === 'my-karaokes') {
      getMyKaraokes()
        .then(setMyKaraokes)
        .catch(() => setError('No se pudieron cargar tus karaokes. Intentá de nuevo.'))
        .finally(() => setLoading(false))
    } else {
      getKaraokeCatalog(source)
        .then(setSongs)
        .catch(() => setError('No se pudieron cargar las canciones. Intentá de nuevo.'))
        .finally(() => setLoading(false))
    }
  }, [source])

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

  const filtered = search
    ? songs.filter((s) => s.title.toLowerCase().includes(search.toLowerCase()))
    : songs

  const filteredMyKaraokes = search
    ? myKaraokes.filter((k) => k.song_title.toLowerCase().includes(search.toLowerCase()))
    : myKaraokes

  return (
    <div className={styles.page}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.pageTitle}>Karaoke</h1>
          <p className={styles.pageSubtitle}>
            Elige una canción y canta con su pista instrumental.
          </p>
        </div>
        <div className={styles.headerActions}>
          {source === 'library' && (
            <button
              type="button"
              onClick={() => setShowUploadModal(true)}
              className={`${styles.headerAction} ${styles.headerActionPrimary}`}
            >
              <Upload size={14} aria-hidden="true" />
              Subir música
            </button>
          )}
          <button onClick={() => setShowJoinModal(true)} className={styles.headerAction}>
            <UsersRound size={14} aria-hidden="true" />
            Unirse a sala
          </button>
        </div>
      </div>

      {showJoinModal && <JoinRoomModal onClose={() => setShowJoinModal(false)} />}
      {showUploadModal && (
        <UploadSongModal onClose={() => setShowUploadModal(false)} onUploaded={handleUploaded} />
      )}

      {/* ── Controls: picker + búsqueda ────────────────────────── */}
      <div className={styles.controls}>
        <div className={styles.sourcePicker}>
          <button
            className={`${styles.sourceBtn} ${source === 'library' ? styles.sourceBtnActive : ''}`}
            onClick={() => setSource('library')}
          >
            Mi Biblioteca
          </button>
          <button
            className={`${styles.sourceBtn} ${source === 'community' ? styles.sourceBtnActive : ''}`}
            onClick={() => setSource('community')}
          >
            Comunidad
          </button>
          <button
            className={`${styles.sourceBtn} ${source === 'my-karaokes' ? styles.sourceBtnActive : ''}`}
            onClick={() => setSource('my-karaokes')}
          >
            Mis Karaokes
          </button>
        </div>

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
            placeholder="Buscar canción..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={styles.searchInput}
          />
        </div>
      </div>

      {/* ── Error ──────────────────────────────────────────────── */}
      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            background: 'var(--color-error-soft)',
            border: '1px solid var(--color-error-border)',
            color: 'var(--color-error)',
            borderRadius: 8,
            padding: '12px 16px',
            fontSize: 14,
            marginBottom: 20,
          }}
        >
          {error}
        </div>
      )}

      {/* ── Skeletons ──────────────────────────────────────────── */}
      {loading && (
        <div className={styles.grid}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className={styles.skeleton} />
          ))}
        </div>
      )}

      {/* ── Grid de canciones ──────────────────────────────────── */}
      {!loading && source !== 'my-karaokes' && filtered.length > 0 && (
        <div className={styles.grid}>
          {filtered.map((song) => (
            <KaraokeSongCard
              key={song.id}
              song={song}
              onSelect={handleSelect}
              isPreviewing={globalTrack?.id === `karaoke-preview:${song.id}` && isPlaying}
              onTogglePreview={handleTogglePreview}
            />
          ))}
        </div>
      )}

      {!loading && source === 'my-karaokes' && filteredMyKaraokes.length > 0 && (
        <div className={styles.grid}>
          {filteredMyKaraokes.map((item) => (
            <MyKaraokeCard key={item.karaoke_id} item={item} onPlay={handlePlayKaraoke} />
          ))}
        </div>
      )}

      {/* ── Estado vacío ───────────────────────────────────────── */}
      {!loading && !error && source !== 'my-karaokes' && filtered.length === 0 && (
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          </div>
          <h3 className={styles.emptyTitle}>
            {search
              ? 'Sin resultados'
              : source === 'library'
                ? 'Tu biblioteca está vacía'
                : 'Sin canciones en la comunidad'}
          </h3>
          <p className={styles.emptyText}>
            {search
              ? 'Probá con otro término de búsqueda.'
              : source === 'library'
                ? 'Generá tu primera canción en "Crear canción".'
                : 'Aún no hay canciones publicadas en la comunidad.'}
          </p>
        </div>
      )}

      {!loading && !error && source === 'my-karaokes' && filteredMyKaraokes.length === 0 && (
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          </div>
          <h3 className={styles.emptyTitle}>
            {search ? 'Sin resultados' : 'Todavía no tenés karaokes generados'}
          </h3>
          <p className={styles.emptyText}>
            {search
              ? 'Probá con otro término de búsqueda.'
              : 'Elegí una canción de tu biblioteca o de la comunidad para empezar.'}
          </p>
        </div>
      )}
    </div>
  )
}
