import { useEffect, useState } from 'react'
import { ArrowRight, AudioWaveform, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getMixProjects, createMixProject, deleteMixProject } from '../../api/modules/mix.api'
import type { MixProject } from '../../api/modules/mix.api'

const STATUS_COLOR: Record<string, string> = {
  draft: 'var(--text-subdued)',
  processing: 'var(--color-warning)',
  ready: 'var(--color-success)',
  failed: 'var(--color-error)',
}

const STATUS_LABEL: Record<string, string> = {
  draft: 'Borrador',
  processing: 'Procesando',
  ready: 'Listo',
  failed: 'Error',
}

export default function MixPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<MixProject[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<MixProject | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    getMixProjects()
      .then(setProjects)
      .catch(() => setError('No se pudieron cargar los proyectos.'))
      .finally(() => setLoading(false))
  }, [])

  async function handleCreate() {
    if (!newTitle.trim()) {
      return
    }
    setCreating(true)
    try {
      const p = await createMixProject({ title: newTitle.trim() })
      setProjects((prev) => [p, ...prev])
      setNewTitle('')
      setShowForm(false)
      navigate(`/mix/${p.id}`)
    } catch {
      setError('No se pudo crear el proyecto.')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    const project = projects.find((item) => item.id === id)
    if (project) {
      setPendingDelete(project)
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return
    }
    const id = pendingDelete.id
    setDeletingId(id)
    setError(null)
    try {
      await deleteMixProject(id)
      setProjects((prev) => prev.filter((p) => p.id !== id))
      setPendingDelete(null)
    } catch {
      setError('No se pudo eliminar el proyecto.')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div style={{ minHeight: '100%', padding: '28px 32px', color: 'var(--text-base)' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 24,
        }}
      >
        <div>
          <h1 style={{ fontSize: 32, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
            Mix DJ
          </h1>
          <p style={{ fontSize: 14, color: 'var(--text-subdued)', margin: '4px 0 0' }}>
            Organiza y mezcla pistas en una línea de tiempo
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          style={{
            background: 'var(--gradient-primary)',
            borderRadius: '500px',
            padding: '10px 20px',
            fontSize: 14,
            fontWeight: 700,
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-base)',
          }}
        >
          + Nuevo proyecto
        </button>
      </div>

      {error && (
        <div
          style={{
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

      {showForm && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 24, alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Nombre del proyecto..."
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            autoFocus
            style={{
              flex: 1,
              maxWidth: 360,
              background: 'var(--bg-card-hover)',
              border: '1px solid var(--color-primary)',
              borderRadius: 4,
              padding: '10px 14px',
              fontSize: 14,
              color: 'var(--text-base)',
              outline: 'none',
            }}
          />
          <button
            onClick={handleCreate}
            disabled={creating || !newTitle.trim()}
            style={{
              padding: '10px 18px',
              borderRadius: 500,
              fontSize: 13,
              fontWeight: 700,
              background: 'var(--gradient-primary)',
              color: 'var(--text-base)',
              border: 'none',
              cursor: 'pointer',
              opacity: creating ? 0.6 : 1,
            }}
          >
            {creating ? 'Creando...' : 'Crear'}
          </button>
          <button
            onClick={() => setShowForm(false)}
            style={{
              padding: '10px 14px',
              borderRadius: 500,
              fontSize: 13,
              background: 'none',
              color: 'var(--text-subdued)',
              border: '1px solid var(--border)',
              cursor: 'pointer',
            }}
          >
            Cancelar
          </button>
        </div>
      )}

      {loading ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 16,
          }}
        >
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              style={{
                height: 130,
                borderRadius: 10,
                background:
                  'linear-gradient(90deg, var(--bg-card-hover) 25%, var(--border-strong) 50%, var(--bg-card-hover) 75%)',
                backgroundSize: '200% 100%',
                animation: 'shimmer 1.5s infinite',
              }}
            />
          ))}
          <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
        </div>
      ) : projects.length === 0 ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: '80px 24px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: '50%',
              background: 'var(--bg-card-hover)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-subdued)',
              marginBottom: 20,
            }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor">
              <path d="M3 9h2v6H3V9zm4-2h2v10H7V7zm4-4h2v18h-2V3zm4 4h2v10h-2V7zm4 2h2v6h-2V9z" />
            </svg>
          </div>
          <h3 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 8px' }}>Sin proyectos de mix</h3>
          <p style={{ fontSize: 14, color: 'var(--text-subdued)', maxWidth: 300 }}>
            Crea tu primer proyecto para combinar canciones estilo DJ.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 16,
          }}
        >
          {projects.map((p) => (
            <div
              key={p.id}
              onClick={() => navigate(`/mix/${p.id}`)}
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 10,
                padding: '16px',
                cursor: 'pointer',
                transition: 'background 0.15s, transform 0.15s',
              }}
              onMouseEnter={(e) => {
                ;(e.currentTarget as HTMLDivElement).style.background = 'var(--bg-card-hover)'
                ;(e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLDivElement).style.background = 'var(--bg-card)'
                ;(e.currentTarget as HTMLDivElement).style.transform = ''
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: 12,
                }}
              >
                <div
                  style={{
                    width: 38,
                    height: 38,
                    borderRadius: 8,
                    background: 'var(--gradient-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <AudioWaveform size={19} color="var(--text-base)" aria-hidden="true" />
                </div>
                <button
                  type="button"
                  onClick={(e) => handleDelete(p.id, e)}
                  aria-label={`Eliminar ${p.title}`}
                  title="Eliminar proyecto"
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--text-subdued)',
                    padding: 6,
                    borderRadius: 6,
                    transition: 'color 0.15s, background 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = 'var(--color-error)'
                    e.currentTarget.style.background = 'var(--color-error-soft)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = 'var(--text-subdued)'
                    e.currentTarget.style.background = 'none'
                  }}
                >
                  <Trash2 size={15} aria-hidden="true" />
                </button>
              </div>
              <p
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                  margin: '0 0 4px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {p.title}
              </p>
              <p style={{ fontSize: 13, color: 'var(--text-subdued)', margin: '0 0 14px' }}>
                {p.clip_count} clip{p.clip_count !== 1 ? 's' : ''}
                {p.bpm ? ` · ${p.bpm} BPM` : ''}
                {p.duration_seconds
                  ? ` · ${Math.floor(p.duration_seconds / 60)}:${String(p.duration_seconds % 60).padStart(2, '0')}`
                  : ''}
              </p>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 10,
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    padding: '3px 10px',
                    borderRadius: 500,
                    background: 'var(--color-primary-soft)',
                    color: STATUS_COLOR[p.status] ?? 'var(--text-base)',
                  }}
                >
                  {STATUS_LABEL[p.status] ?? p.status}
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/mix/${p.id}`)
                  }}
                  aria-label={`Abrir ${p.title}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: 0,
                    border: 'none',
                    background: 'none',
                    color: 'var(--color-primary)',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Abrir
                  <ArrowRight size={14} aria-hidden="true" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {pendingDelete && (
        <div
          role="presentation"
          onClick={() => deletingId === null && setPendingDelete(null)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 100,
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
            aria-labelledby="delete-mix-title"
            onClick={(event) => event.stopPropagation()}
            style={{
              width: 'min(100%, 400px)',
              padding: 24,
              borderRadius: 12,
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              boxShadow: 'var(--shadow)',
            }}
          >
            <h2 id="delete-mix-title" style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 700 }}>
              ¿Eliminar proyecto?
            </h2>
            <p style={{ margin: '0 0 20px', color: 'var(--text-subdued)', fontSize: 14 }}>
              Se eliminará “{pendingDelete.title}” y no podrás recuperar sus clips.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setPendingDelete(null)}
                disabled={deletingId !== null}
                style={{
                  padding: '9px 16px',
                  borderRadius: 500,
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--text-base)',
                  cursor: 'pointer',
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => void confirmDelete()}
                disabled={deletingId !== null}
                style={{
                  padding: '9px 16px',
                  borderRadius: 500,
                  border: 'none',
                  background: 'var(--color-error)',
                  color: 'white',
                  fontWeight: 700,
                  cursor: 'pointer',
                  opacity: deletingId !== null ? 0.6 : 1,
                }}
              >
                {deletingId !== null ? 'Eliminando...' : 'Eliminar proyecto'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
