import { useEffect, useState } from 'react'
import { LoaderCircle, Pause, Play, Share2 } from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getPlaylist,
  sharePlaylist,
  deletePlaylist,
  updatePlaylist,
  addSongToPlaylist,
  removeSongFromPlaylist,
  getPlaylistCoverUrl,
} from '../../api/modules/playlists.api'
import type { Playlist, PlaylistSongItem } from '../../api/modules/playlists.api'
import { getSongPlayUrl, getLibrary } from '../../api/modules/songs.api'
import type { LibrarySong } from '../../api/modules/songs.api'
import LyricsView from '../../components/song/lyrics-view'
import PlaylistSongRow from '../../components/playlists/playlist-song-row'
import { useGlobalAudioPlayer } from '../../components/player/use-global-audio-player'
import styles from './playlist-detail-page.module.css'

export default function PlaylistDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [playlist, setPlaylist] = useState<Playlist | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [sharing, setSharing] = useState(false)
  const [activeSongId, setActiveSongId] = useState<string | null>(null)
  const [loadingPlay, setLoadingPlay] = useState(false)
  const [playUrls, setPlayUrls] = useState<Record<string, string>>({})

  const [showLyrics, setShowLyrics] = useState(false)
  const [activeSong, setActiveSong] = useState<PlaylistSongItem | null>(null)
  const {
    track: globalTrack,
    isPlaying,
    playTrack,
    pause,
    updateTrack,
    close,
    audioRef,
  } = useGlobalAudioPlayer()

  const [showAddModal, setShowAddModal] = useState(false)
  const [libraryForAdd, setLibraryForAdd] = useState<LibrarySong[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [addSearch, setAddSearch] = useState('')
  const [adding, setAdding] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<PlaylistSongItem | null>(null)
  const [removingSongId, setRemovingSongId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [addError, setAddError] = useState<string | null>(null)
  const [addLoading, setAddLoading] = useState(false)
  const [editingDetails, setEditingDetails] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [savingDetails, setSavingDetails] = useState(false)

  useEffect(() => {
    if (!id) {
      return
    }
    setLoading(true)
    getPlaylist(id)
      .then(setPlaylist)
      .catch(() => setError('No se pudo cargar la playlist.'))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!playlist) {
      return
    }
    let cancelled = false
    playlist.playlist_songs.forEach((item) => {
      getSongPlayUrl(item.song.id)
        .then((url) => {
          if (!cancelled) {
            setPlayUrls((current) => ({ ...current, [item.song.id]: url }))
          }
        })
        .catch(() => {})
    })
    return () => {
      cancelled = true
    }
  }, [playlist])

  useEffect(() => {
    if (!showAddModal) {
      return
    }
    setAddError(null)
    setAddLoading(true)
    getLibrary()
      .then(setLibraryForAdd)
      .catch(() => setAddError('No se pudo cargar tu biblioteca.'))
      .finally(() => setAddLoading(false))
  }, [showAddModal])

  async function handleShare() {
    if (!id) {
      return
    }
    setSharing(true)
    try {
      const { share_url: rawShareUrl } = await sharePlaylist(id)
      const full = new URL(rawShareUrl, window.location.origin).href
      setShareUrl(full)
      await navigator.clipboard.writeText(full).catch(() => {})
    } catch {
      setError('No se pudo generar el enlace.')
    } finally {
      setSharing(false)
    }
  }

  function startEditingDetails() {
    if (!playlist) {
      return
    }
    setEditTitle(playlist.title)
    setEditDescription(playlist.description ?? '')
    setActionError(null)
    setEditingDetails(true)
  }

  async function handleSaveDetails() {
    if (!id || !editTitle.trim()) {
      setActionError('El nombre de la playlist no puede estar vacío.')
      return
    }
    setSavingDetails(true)
    setActionError(null)
    try {
      const updated = await updatePlaylist(id, {
        title: editTitle.trim(),
        description: editDescription.trim(),
      })
      setPlaylist((current) => (current ? { ...current, ...updated } : updated))
      setEditingDetails(false)
    } catch {
      setActionError('No se pudo actualizar la playlist.')
    } finally {
      setSavingDetails(false)
    }
  }

  async function handlePlay(item: PlaylistSongItem) {
    const trackId = `song:${item.song.id}`
    if (globalTrack?.id === trackId) {
      if (isPlaying) {
        pause()
      } else {
        playTrack(globalTrack)
      }
      return
    }
    setShowLyrics(false)
    setLoadingPlay(true)
    setActiveSongId(item.song.id)
    setActiveSong(item)
    try {
      const url = playUrls[item.song.id] ?? (await getSongPlayUrl(item.song.id))
      setPlayUrls((current) => ({ ...current, [item.song.id]: url }))
      playTrack({
        id: trackId,
        audioUrl: url,
        title: item.song.title ?? 'Sin título',
        subtitle: item.song.genre ?? undefined,
        coverUrl: item.song.thumbnail_url,
        showLyrics: false,
        onToggleLyrics: () => {
          setShowLyrics((value) => {
            updateTrack({ showLyrics: !value })
            return !value
          })
        },
        onEnded: () => {
          const ordered = (playlist?.playlist_songs ?? [])
            .slice()
            .sort((a, b) => a.position - b.position)
          const currentIndex = ordered.findIndex((song) => song.song.id === item.song.id)
          const nextSong = ordered[currentIndex + 1]
          if (nextSong) {
            void handlePlay(nextSong)
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
    } finally {
      setLoadingPlay(false)
    }
  }

  async function handlePlayAll() {
    const firstSong = (playlist?.playlist_songs ?? [])
      .slice()
      .sort((a, b) => a.position - b.position)[0]
    if (firstSong) {
      await handlePlay(firstSong)
    }
  }

  async function handleRemoveSong() {
    if (!id || !removeTarget) {
      return
    }

    setRemovingSongId(removeTarget.song.id)
    setActionError(null)
    try {
      await removeSongFromPlaylist(id, removeTarget.song.id)
      if (activeSongId === removeTarget.song.id) {
        close()
        setActiveSongId(null)
        setActiveSong(null)
      }
      setPlaylist((prev) =>
        prev
          ? {
              ...prev,
              playlist_songs: prev.playlist_songs.filter((item) => item.id !== removeTarget.id),
            }
          : prev
      )
      setRemoveTarget(null)
    } catch {
      setActionError('No se pudo quitar la canción de la playlist.')
    } finally {
      setRemovingSongId(null)
    }
  }

  async function handleAddSongs() {
    if (!id || selectedIds.size === 0) {
      return
    }

    setAdding(true)
    setAddError(null)
    const failedIds: string[] = []
    try {
      for (const songId of selectedIds) {
        try {
          await addSongToPlaylist(id, songId)
        } catch {
          failedIds.push(songId)
        }
      }

      if (failedIds.length > 0) {
        setAddError(
          failedIds.length === selectedIds.size
            ? 'No se pudo agregar ninguna canción.'
            : `No se pudieron agregar ${failedIds.length} canciones.`
        )
        return
      }

      const updated = await getPlaylist(id)
      setPlaylist(updated)
      setShowAddModal(false)
      setSelectedIds(new Set())
      setAddSearch('')
    } catch {
      setAddError('No se pudo actualizar la playlist.')
    } finally {
      setAdding(false)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '28px 32px', color: 'var(--text-base)' }}>
        <p style={{ color: 'var(--text-subdued)', fontSize: 14 }}>Cargando playlist...</p>
      </div>
    )
  }

  if (error || !playlist) {
    return (
      <div style={{ padding: '28px 32px', color: 'var(--text-base)' }}>
        <p style={{ color: 'var(--color-error)', fontSize: 14 }}>
          {error ?? 'Playlist no encontrada.'}
        </p>
        <button
          onClick={() => navigate('/playlists')}
          style={{
            marginTop: 12,
            color: 'var(--color-primary)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: 14,
          }}
        >
          ← Volver a playlists
        </button>
      </div>
    )
  }

  const songs = playlist.playlist_songs ?? []
  const orderedSongs = songs.slice().sort((a, b) => a.position - b.position)
  const firstSong = orderedSongs[0]
  const isFirstSongPlaying = firstSong?.song.id === activeSongId && isPlaying
  const availableAddSongs = libraryForAdd
    .filter((song) => !songs.some((item) => item.song.id === song.id))
    .filter((song) => {
      const query = addSearch.trim().toLowerCase()
      return !query || song.title.toLowerCase().includes(query)
    })
  const coverUrl = getPlaylistCoverUrl(playlist)

  return (
    <div style={{ minHeight: '100%', padding: '28px 32px 80px', color: 'var(--text-base)' }}>
      {/* Back */}
      <button
        onClick={() => navigate('/playlists')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          color: 'var(--text-subdued)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 14,
          marginBottom: 20,
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
        </svg>
        Volver
      </button>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 24 }}>
        <div
          style={{
            width: 128,
            height: 128,
            borderRadius: 12,
            background: 'var(--bg-card-hover)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-subdued)',
            flexShrink: 0,
            overflow: 'hidden',
          }}
        >
          {coverUrl ? (
            <img
              src={coverUrl}
              alt=""
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
          ) : (
            <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
              <path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18A3 3 0 1 0 19 17V8h3V6h-5z" />
            </svg>
          )}
        </div>
        <div style={{ flex: 1 }}>
          <p
            style={{
              fontSize: 12,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'var(--text-subdued)',
              margin: '0 0 6px',
            }}
          >
            {playlist.type === 'manual' ? 'Playlist' : 'Playlist automática'}
          </p>
          {editingDetails ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 520 }}>
              <input
                value={editTitle}
                onChange={(event) => setEditTitle(event.target.value)}
                aria-label="Nombre de la playlist"
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-card-hover)',
                  color: 'var(--text-base)',
                  fontSize: 24,
                  fontWeight: 700,
                }}
              />
              <textarea
                value={editDescription}
                onChange={(event) => setEditDescription(event.target.value)}
                placeholder="Descripción breve"
                aria-label="Descripción de la playlist"
                rows={2}
                style={{
                  resize: 'none',
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-card-hover)',
                  color: 'var(--text-base)',
                  fontSize: 14,
                }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  onClick={handleSaveDetails}
                  disabled={savingDetails}
                  style={{
                    padding: '7px 12px',
                    border: 'none',
                    borderRadius: 8,
                    background: 'var(--color-primary)',
                    color: 'var(--bg-base)',
                    fontWeight: 700,
                    cursor: savingDetails ? 'wait' : 'pointer',
                  }}
                >
                  {savingDetails ? 'Guardando...' : 'Guardar'}
                </button>
                <button
                  type="button"
                  onClick={() => setEditingDetails(false)}
                  disabled={savingDetails}
                  style={{
                    padding: '7px 12px',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    background: 'none',
                    color: 'var(--text-base)',
                    cursor: 'pointer',
                  }}
                >
                  Cancelar
                </button>
              </div>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h1
                  style={{
                    fontSize: 32,
                    fontWeight: 700,
                    margin: '0 0 8px',
                    letterSpacing: '-0.02em',
                  }}
                >
                  {playlist.title}
                </h1>
                <button
                  type="button"
                  onClick={startEditingDetails}
                  aria-label="Editar playlist"
                  title="Editar playlist"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 30,
                    height: 30,
                    marginBottom: 8,
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    background: 'none',
                    color: 'var(--text-subdued)',
                    cursor: 'pointer',
                  }}
                >
                  ✎
                </button>
              </div>
              {playlist.description && (
                <p style={{ fontSize: 14, color: 'var(--text-subdued)', margin: '0 0 12px' }}>
                  {playlist.description}
                </p>
              )}
            </>
          )}
          <p style={{ fontSize: 14, color: 'var(--text-subdued)', margin: '0 0 16px' }}>
            {songs.length} canción{songs.length !== 1 ? 'es' : ''}
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={handlePlayAll}
              disabled={songs.length === 0 || loadingPlay}
              aria-label={isFirstSongPlaying ? 'Pausar playlist' : 'Reproducir playlist'}
              title={isFirstSongPlaying ? 'Pausar playlist' : 'Reproducir playlist'}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                minWidth: 150,
                justifyContent: 'center',
                padding: '8px 18px',
                borderRadius: 500,
                fontSize: 13,
                fontWeight: 700,
                background: 'var(--color-primary)',
                color: 'var(--bg-base)',
                border: 'none',
                cursor: songs.length === 0 || loadingPlay ? 'not-allowed' : 'pointer',
                opacity: songs.length === 0 || loadingPlay ? 0.5 : 1,
              }}
            >
              {loadingPlay ? (
                <LoaderCircle size={14} aria-hidden="true" className="animate-spin" />
              ) : isFirstSongPlaying ? (
                <Pause size={14} fill="currentColor" aria-hidden="true" />
              ) : (
                <Play size={14} fill="currentColor" aria-hidden="true" />
              )}
              Reproducir todo
            </button>
            <button
              onClick={async () => {
                if (!id || !window.confirm(`¿Eliminar la playlist "${playlist.title}"?`)) {
                  return
                }
                await deletePlaylist(id)
                navigate('/playlists')
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 18px',
                borderRadius: 500,
                fontSize: 13,
                fontWeight: 600,
                background: 'none',
                color: 'var(--color-error)',
                border: '1px solid var(--color-error)',
                cursor: 'pointer',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
              </svg>
              Eliminar
            </button>

            <button
              onClick={() => setShowAddModal(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 18px',
                borderRadius: 500,
                fontSize: 13,
                fontWeight: 600,
                background: 'var(--bg-card-hover)',
                color: 'var(--text-base)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              + Agregar canciones
            </button>

            <button
              type="button"
              onClick={handleShare}
              disabled={sharing}
              aria-label={sharing ? 'Compartiendo playlist' : 'Compartir playlist'}
              title={sharing ? 'Compartiendo...' : 'Compartir playlist'}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                width: 36,
                height: 36,
                justifyContent: 'center',
                padding: 0,
                borderRadius: 500,
                fontSize: 13,
                fontWeight: 600,
                background: 'var(--bg-card-hover)',
                color: 'var(--text-base)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
                opacity: sharing ? 0.6 : 1,
                transition: 'opacity 0.15s',
              }}
            >
              <Share2 size={15} strokeWidth={2} aria-hidden="true" />
            </button>
          </div>
          {shareUrl && (
            <p style={{ marginTop: 10, fontSize: 13, color: 'var(--color-success)' }}>
              ✓ Enlace copiado:{' '}
              <span style={{ color: 'var(--text-subdued)', wordBreak: 'break-all' }}>
                {shareUrl}
              </span>
            </p>
          )}
          {actionError && (
            <p
              style={{
                margin: '10px 0 0',
                padding: '10px 12px',
                borderRadius: 8,
                background: 'var(--color-error-soft)',
                color: 'var(--color-error)',
                fontSize: 13,
              }}
            >
              {actionError}
            </p>
          )}
        </div>
      </div>

      {/* Song list */}
      {songs.length === 0 ? (
        <div
          style={{
            padding: '40px 0',
            textAlign: 'center',
            color: 'var(--text-subdued)',
            fontSize: 14,
          }}
        >
          Esta playlist está vacía. Agrega canciones desde tu biblioteca.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {orderedSongs.map((item, index) => (
            <PlaylistSongRow
              key={item.id}
              item={item}
              index={index}
              active={activeSongId === item.song.id}
              playing={activeSongId === item.song.id && isPlaying}
              loading={loadingPlay && activeSongId === item.song.id}
              onPlay={() => handlePlay(item)}
              onRemove={() => setRemoveTarget(item)}
            />
          ))}
        </div>
      )}

      {showLyrics && activeSong && (
        <LyricsView
          song={activeSong.song as unknown as LibrarySong}
          audioRef={audioRef}
          onClose={() => setShowLyrics(false)}
        />
      )}

      {removeTarget && (
        <div
          role="presentation"
          onClick={() => {
            if (!removingSongId) {
              setRemoveTarget(null)
            }
          }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 110,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
            background: 'var(--overlay)',
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="remove-song-title"
            onClick={(event) => event.stopPropagation()}
            style={{
              width: 'min(100%, 380px)',
              padding: 22,
              borderRadius: 12,
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              boxShadow: 'var(--shadow)',
            }}
          >
            <h2 id="remove-song-title" style={{ margin: '0 0 8px', fontSize: 18 }}>
              Quitar canción
            </h2>
            <p style={{ margin: '0 0 20px', color: 'var(--text-subdued)', fontSize: 14 }}>
              ¿Quieres quitar “{removeTarget.song.title ?? 'Sin título'}” de esta playlist?
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                onClick={() => setRemoveTarget(null)}
                disabled={Boolean(removingSongId)}
                style={{
                  padding: '8px 14px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'none',
                  color: 'var(--text-base)',
                  cursor: 'pointer',
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleRemoveSong}
                disabled={Boolean(removingSongId)}
                style={{
                  padding: '8px 14px',
                  borderRadius: 8,
                  border: 'none',
                  background: 'var(--color-error)',
                  color: 'var(--bg-base)',
                  fontWeight: 700,
                  cursor: removingSongId ? 'wait' : 'pointer',
                  opacity: removingSongId ? 0.6 : 1,
                }}
              >
                {removingSongId ? 'Quitando...' : 'Quitar de la playlist'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal agregar canciones */}
      {showAddModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'var(--overlay)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              background: 'var(--bg-surface)',
              borderRadius: 12,
              padding: 24,
              width: 420,
              maxHeight: '70vh',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Agregar canciones</h2>
              <button
                onClick={() => {
                  setShowAddModal(false)
                  setSelectedIds(new Set())
                  setAddSearch('')
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-subdued)',
                  cursor: 'pointer',
                  fontSize: 20,
                }}
              >
                ✕
              </button>
            </div>
            <input
              type="search"
              value={addSearch}
              onChange={(event) => setAddSearch(event.target.value)}
              placeholder="Buscar canciones..."
              style={{
                width: '100%',
                boxSizing: 'border-box',
                padding: '9px 11px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-card-hover)',
                color: 'var(--text-base)',
                outline: 'none',
                fontSize: 13,
              }}
            />
            {addError && (
              <p style={{ margin: 0, color: 'var(--color-error)', fontSize: 13 }}>{addError}</p>
            )}
            <div
              style={{
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                flex: 1,
              }}
            >
              {addLoading ? (
                <p style={{ margin: 'auto', color: 'var(--text-subdued)', fontSize: 13 }}>
                  Cargando canciones...
                </p>
              ) : availableAddSongs.length === 0 ? (
                <p style={{ margin: 'auto', color: 'var(--text-subdued)', fontSize: 13 }}>
                  {addSearch
                    ? 'No hay coincidencias.'
                    : 'No hay canciones disponibles para agregar.'}
                </p>
              ) : (
                availableAddSongs.map((s) => (
                  <label
                    key={s.id}
                    className={`${styles.addSongRow} ${selectedIds.has(s.id) ? styles.addSongRowSelected : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(s.id)}
                      onChange={() => {
                        const next = new Set(selectedIds)
                        if (next.has(s.id)) {
                          next.delete(s.id)
                        } else {
                          next.add(s.id)
                        }
                        setSelectedIds(next)
                      }}
                      style={{ accentColor: 'var(--color-primary)' }}
                    />
                    {s.thumbnail_url ? (
                      <img src={s.thumbnail_url} alt="" className={styles.addSongThumb} />
                    ) : (
                      <div className={styles.addSongThumb} />
                    )}
                    <span style={{ fontSize: 14, color: 'var(--text-base)' }}>{s.title}</span>
                  </label>
                ))
              )}
            </div>
            <button
              disabled={selectedIds.size === 0 || adding}
              onClick={handleAddSongs}
              style={{
                padding: '10px',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 700,
                background: 'var(--color-primary)',
                color: 'var(--bg-base)',
                border: 'none',
                cursor: 'pointer',
                opacity: selectedIds.size === 0 || adding ? 0.5 : 1,
              }}
            >
              {adding
                ? 'Agregando...'
                : `Agregar ${selectedIds.size} canción${selectedIds.size !== 1 ? 'es' : ''}`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
