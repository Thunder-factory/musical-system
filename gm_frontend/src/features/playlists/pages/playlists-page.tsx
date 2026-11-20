import { useEffect, useState } from 'react'
import { ListMusic, Plus, RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button, EmptyState } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import {
  generateAutoPlaylists,
  getAutoPlaylists,
  getPlaylists,
  type Playlist,
} from '../api/playlists.api'
import CreatePlaylistModal from '../components/create-playlist-modal'
import PlaylistCard from '../components/playlist-card'

type Tab = 'manual' | 'auto'

export default function PlaylistsPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('manual')
  const [manual, setManual] = useState<Playlist[]>([])
  const [auto, setAuto] = useState<Playlist[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([getPlaylists(), getAutoPlaylists()])
      .then(([m, a]) => {
        setManual(m)
        setAuto(a)
      })
      .catch(() => setError('No se pudieron cargar las playlists.'))
      .finally(() => setLoading(false))
  }, [])

  async function handleGenerateAuto() {
    setGenerating(true)
    setError(null)
    try {
      await generateAutoPlaylists()
      setAuto(await getAutoPlaylists())
      toast.success('Playlists automáticas actualizadas')
    } catch {
      toast.error('No se pudieron generar las playlists automáticas')
    } finally {
      setGenerating(false)
    }
  }

  function handleCreated(playlist: Playlist) {
    setManual((prev) => [playlist, ...prev])
    setShowCreate(false)
    navigate(`/playlists/${playlist.id}`)
  }

  const list = tab === 'manual' ? manual : auto

  return (
    <div className="min-h-full px-6 pb-20 pt-7 text-white sm:px-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Playlists</h1>
          <p className="mt-1 text-sm text-muted">
            {tab === 'manual'
              ? 'Organiza tus canciones en playlists.'
              : 'Playlists creadas según tus gustos.'}
          </p>
        </div>
        {tab === 'manual' && (
          <Button
            variant="primary"
            leftIcon={<Plus size={15} />}
            onClick={() => setShowCreate(true)}
          >
            Nueva playlist
          </Button>
        )}
      </header>

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          {error}
        </div>
      )}

      <div className="mb-6 flex gap-1 border-b border-border">
        {(
          [
            ['manual', 'Mis playlists'],
            ['auto', 'Automáticas'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm transition-colors ${
              tab === key
                ? 'border-primary font-bold text-white'
                : 'border-transparent text-muted hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'auto' && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted">
            Se generan automáticamente a partir de tus géneros y ambientes más escuchados.
          </p>
          <Button
            variant="secondary"
            size="sm"
            loading={generating}
            leftIcon={<RefreshCw size={14} />}
            onClick={() => void handleGenerateAuto()}
          >
            {generating ? 'Generando...' : 'Regenerar'}
          </Button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-64 animate-pulse rounded-xl bg-card-hover" />
          ))}
        </div>
      ) : list.length > 0 ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
          {list.map((p) => (
            <PlaylistCard key={p.id} playlist={p} />
          ))}
        </div>
      ) : tab === 'manual' ? (
        <EmptyState
          icon={<ListMusic size={24} />}
          title="Aún no tienes playlists"
          description="Crea tu primera playlist para organizar tus canciones favoritas."
          actionLabel="Nueva playlist"
          onAction={() => setShowCreate(true)}
        />
      ) : (
        <EmptyState
          icon={<ListMusic size={24} />}
          title="Sin playlists automáticas"
          description="Genera colecciones según tus géneros y estados de ánimo."
          actionLabel="Generar automáticas"
          onAction={() => void handleGenerateAuto()}
        />
      )}

      <CreatePlaylistModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={handleCreated}
      />
    </div>
  )
}
