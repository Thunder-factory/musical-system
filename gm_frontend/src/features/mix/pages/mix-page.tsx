import { useEffect, useState } from 'react'
import { AudioWaveform, Plus } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { Button, EmptyState, useConfirm } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { getSongDetail } from '../../songs/api/songs.api'
import { deleteMixProject, getMixProjects, type MixProject } from '../api/mix.api'
import CreateMixModal from '../components/create-mix-modal'
import MixProjectCard from '../components/mix-project-card'

export default function MixPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const pendingSongId = searchParams.get('songId')
  const confirm = useConfirm()

  const [projects, setProjects] = useState<MixProject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [pendingSongTitle, setPendingSongTitle] = useState<string | null>(null)

  useEffect(() => {
    getMixProjects()
      .then(setProjects)
      .catch(() => setError('No se pudieron cargar los proyectos.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!pendingSongId) {
      setPendingSongTitle(null)
      return
    }
    getSongDetail(pendingSongId)
      .then((song) => setPendingSongTitle(song.title))
      .catch(() => setPendingSongTitle(null))
  }, [pendingSongId])

  async function handleDelete(project: MixProject) {
    const accepted = await confirm({
      title: '¿Eliminar proyecto?',
      description: `Se eliminará “${project.title}” y no podrás recuperar sus clips.`,
      confirmLabel: 'Eliminar proyecto',
      variant: 'danger',
    })
    if (!accepted) {
      return
    }
    try {
      await deleteMixProject(project.id)
      setProjects((prev) => prev.filter((p) => p.id !== project.id))
      toast.success('Proyecto eliminado')
    } catch {
      toast.error('No se pudo eliminar el proyecto')
    }
  }

  function handleCreated(project: MixProject) {
    setProjects((prev) => [project, ...prev])
    setShowCreate(false)
    navigate(`/mix/${project.id}`)
  }

  function handleAddToProject(projectId: string) {
    if (pendingSongId) {
      navigate(`/mix/${projectId}?addSongId=${encodeURIComponent(pendingSongId)}`)
    }
  }

  return (
    <div className="min-h-full px-6 pb-20 pt-7 text-white sm:px-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Mix DJ</h1>
          <p className="mt-1 text-sm text-muted">
            Organiza y mezcla pistas en una línea de tiempo.
          </p>
        </div>
        <Button variant="primary" leftIcon={<Plus size={15} />} onClick={() => setShowCreate(true)}>
          Nuevo proyecto
        </Button>
      </header>

      {pendingSongId && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary-border bg-primary-soft px-4 py-3 text-sm">
          <p className="text-white">
            Canción lista para mezclar:{' '}
            <strong className="text-primary">{pendingSongTitle ?? 'Canción seleccionada'}</strong>.
            Crea un proyecto nuevo con ella o añádela a uno existente.
          </p>
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm" onClick={() => setShowCreate(true)}>
              Crear proyecto con esta canción
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                searchParams.delete('songId')
                setSearchParams(searchParams, { replace: true })
              }}
            >
              Omitir
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-36 animate-pulse rounded-xl bg-card-hover" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <EmptyState
          icon={<AudioWaveform size={24} />}
          title="Sin proyectos de mix"
          description="Crea tu primer proyecto para combinar canciones estilo DJ."
          actionLabel={pendingSongId ? 'Crear proyecto con esta canción' : 'Crear proyecto'}
          onAction={() => setShowCreate(true)}
        />
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
          {projects.map((p) => (
            <MixProjectCard
              key={p.id}
              project={p}
              pendingSongId={pendingSongId}
              onDelete={handleDelete}
              onAddSongToProject={handleAddToProject}
            />
          ))}
        </div>
      )}

      <CreateMixModal
        open={showCreate}
        initialSongId={pendingSongId}
        initialSongTitle={pendingSongTitle}
        onClose={() => setShowCreate(false)}
        onCreated={handleCreated}
      />
    </div>
  )
}
