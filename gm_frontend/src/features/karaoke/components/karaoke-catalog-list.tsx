import { Mic2, Music2, Pause, Play } from 'lucide-react'

import { Badge, Button, EmptyState } from '../../../components/ui'
import type { KaraokeCatalogSong, MyKaraokeItem } from '../../../types'

type Source = 'library' | 'community' | 'my-karaokes'

interface KaraokeCatalogListProps {
  source: Source
  songs: KaraokeCatalogSong[]
  myKaraokes: MyKaraokeItem[]
  search: string
  activeTrackId?: string
  isPlaying: boolean
  onSelectSong: (song: KaraokeCatalogSong) => void
  onTogglePreview: (song: KaraokeCatalogSong) => void
  onPlayMyKaraoke: (item: MyKaraokeItem) => void
  onOpenUpload: () => void
  onClearSearch: () => void
}

const STATUS_BADGE: Record<
  MyKaraokeItem['status'],
  { label: string; variant: 'neutral' | 'warning' | 'error' | 'success' }
> = {
  ready: { label: 'Listo', variant: 'success' },
  queued: { label: 'En cola', variant: 'warning' },
  processing: { label: 'Procesando', variant: 'warning' },
  failed: { label: 'Error', variant: 'error' },
}

export default function KaraokeCatalogList({
  source,
  songs,
  myKaraokes,
  search,
  activeTrackId,
  isPlaying,
  onSelectSong,
  onTogglePreview,
  onPlayMyKaraoke,
  onOpenUpload,
  onClearSearch,
}: KaraokeCatalogListProps) {
  if (source !== 'my-karaokes' && songs.length === 0) {
    if (search) {
      return (
        <EmptyState
          icon={<Mic2 size={24} />}
          title="Sin resultados"
          description="Prueba con otro término de búsqueda."
          actionLabel="Limpiar búsqueda"
          onAction={onClearSearch}
        />
      )
    }
    return source === 'library' ? (
      <EmptyState
        icon={<Mic2 size={24} />}
        title="Tu biblioteca está vacía"
        description="Sube una pista de audio o genera tu primera canción para cantar en modo karaoke."
        actionLabel="Subir música"
        onAction={onOpenUpload}
      />
    ) : (
      <EmptyState
        icon={<Mic2 size={24} />}
        title="Sin canciones en la comunidad"
        description="Aún no hay canciones públicas en la comunidad. También puedes crear una desde tu estudio."
        actionLabel="Crear canción"
        actionTo="/create"
      />
    )
  }

  if (source === 'my-karaokes' && myKaraokes.length === 0) {
    return search ? (
      <EmptyState
        icon={<Mic2 size={24} />}
        title="Sin resultados"
        description="Prueba con otro término de búsqueda."
        actionLabel="Limpiar búsqueda"
        onAction={onClearSearch}
      />
    ) : (
      <EmptyState
        icon={<Mic2 size={24} />}
        title="Todavía no tienes karaokes"
        description="Elige una canción de tu biblioteca o crea una nueva canción para generar tu primer karaoke."
        actionLabel="Crear canción"
        actionTo="/create"
      />
    )
  }

  if (source === 'my-karaokes') {
    return (
      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
        {myKaraokes.map((item) => {
          const isReady = item.status === 'ready'
          const badge = STATUS_BADGE[item.status]
          return (
            <article
              key={item.karaoke_id}
              className="flex flex-col overflow-hidden rounded-xl border border-border bg-card transition-transform hover:-translate-y-0.5"
            >
              <div className="relative aspect-square w-full overflow-hidden bg-card-hover">
                {item.thumbnail_url ? (
                  <img
                    src={item.thumbnail_url}
                    alt={`Portada de ${item.song_title}`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-muted">
                    <Music2 size={36} aria-hidden="true" />
                  </div>
                )}
                {!isReady && (
                  <div className="absolute inset-0 flex items-center justify-center bg-[var(--overlay)]">
                    <Badge variant={badge.variant}>{badge.label}</Badge>
                  </div>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-3 p-3.5">
                <p className="truncate text-sm font-semibold text-white">{item.song_title}</p>
                <Button
                  variant="primary"
                  size="sm"
                  className="mt-auto w-full"
                  leftIcon={<Mic2 size={14} />}
                  disabled={!isReady}
                  onClick={() => onPlayMyKaraoke(item)}
                >
                  Cantar
                </Button>
              </div>
            </article>
          )
        })}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
      {songs.map((song) => {
        const previewing = activeTrackId === `karaoke-preview:${song.id}` && isPlaying
        const tags = song.tags?.slice(0, 3) ?? []
        return (
          <article
            key={song.id}
            className="group flex flex-col overflow-hidden rounded-xl border border-border bg-card transition-transform hover:-translate-y-0.5"
          >
            <div className="relative aspect-square w-full overflow-hidden bg-card-hover">
              {song.thumbnail_url ? (
                <img
                  src={song.thumbnail_url}
                  alt={`Portada de ${song.title}`}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-muted">
                  <Music2 size={36} aria-hidden="true" />
                </div>
              )}
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-night via-transparent to-transparent" />
              <button
                type="button"
                onClick={() => onTogglePreview(song)}
                aria-label={previewing ? `Pausar ${song.title}` : `Reproducir ${song.title}`}
                className={`absolute bottom-2.5 right-2.5 flex h-10 w-10 items-center justify-center rounded-full shadow-[var(--shadow)] transition-all ${
                  previewing
                    ? 'bg-primary text-black opacity-100'
                    : 'bg-white text-black opacity-0 group-hover:opacity-100 focus-visible:opacity-100'
                }`}
              >
                {previewing ? (
                  <Pause size={16} fill="currentColor" aria-hidden="true" />
                ) : (
                  <Play size={16} fill="currentColor" aria-hidden="true" />
                )}
              </button>
            </div>

            <div className="flex flex-1 flex-col gap-2.5 p-3.5">
              <div>
                <p className="truncate text-sm font-semibold text-white">{song.title}</p>
                {song.user_name && <p className="truncate text-xs text-muted">por {song.user_name}</p>}
              </div>

              {tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {tags.map((tag) => (
                    <Badge key={tag} variant="neutral">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}

              <Button
                variant="primary"
                size="sm"
                className="mt-auto w-full"
                leftIcon={<Mic2 size={14} />}
                onClick={() => onSelectSong(song)}
              >
                Karaoke
              </Button>
            </div>
          </article>
        )
      })}
    </div>
  )
}
