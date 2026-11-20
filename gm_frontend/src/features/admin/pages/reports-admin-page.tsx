import { useEffect, useState, type ReactNode } from 'react'
import { AlertCircle, CheckCircle2, Globe, Music2, UserPlus, Users } from 'lucide-react'

import { Badge } from '../../../components/ui'
import { adminApi, type TopSong, type UsageStats } from '../api/admin.api'

function StatCard({
  label,
  value,
  sublabel,
  toneClass = 'text-primary',
  icon,
}: {
  label: string
  value: number | string
  sublabel?: string
  toneClass?: string
  icon: ReactNode
}) {
  return (
    <div className="flex flex-col gap-2.5 rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted">{label}</span>
        <div
          className={`flex h-9 w-9 items-center justify-center rounded-lg bg-card-hover ${toneClass}`}
        >
          {icon}
        </div>
      </div>
      <div>
        <p className="text-2xl font-bold tracking-tight tabular-nums text-white">
          {typeof value === 'number' ? value.toLocaleString('es-ES') : value}
        </p>
        {sublabel && <p className="mt-1 text-xs text-muted">{sublabel}</p>}
      </div>
    </div>
  )
}

export default function ReportsAdminPage() {
  const [stats, setStats] = useState<UsageStats | null>(null)
  const [topSongs, setTopSongs] = useState<TopSong[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([adminApi.getUsageStats(), adminApi.getTopSongs()])
      .then(([u, t]) => {
        setStats(u)
        setTopSongs(t)
      })
      .catch(() => setError('No se pudieron cargar los reportes.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6 p-6 text-white">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Reportes</h1>
        <p className="mt-1 text-sm text-muted">Estadísticas de uso de la plataforma.</p>
      </header>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-card-hover" />
          ))
        ) : stats ? (
          <>
            <StatCard
              label="Total usuarios"
              value={stats.total_users}
              sublabel={`+${stats.new_users_30d} en los últimos 30 días`}
              icon={<Users size={18} aria-hidden="true" />}
            />
            <StatCard
              label="Canciones generadas"
              value={stats.total_songs_generated}
              sublabel={`${stats.songs_last_30d} en los últimos 30 días`}
              toneClass="text-success"
              icon={<Music2 size={18} aria-hidden="true" />}
            />
            <StatCard
              label="Canciones públicas"
              value={stats.public_songs}
              sublabel="Visibles en la comunidad"
              toneClass="text-info"
              icon={<Globe size={18} aria-hidden="true" />}
            />
            <StatCard
              label="Nuevos usuarios (30d)"
              value={stats.new_users_30d}
              toneClass="text-warning"
              icon={<UserPlus size={18} aria-hidden="true" />}
            />
            <StatCard
              label="Canciones (30d)"
              value={stats.songs_last_30d}
              toneClass="text-success"
              icon={<CheckCircle2 size={18} aria-hidden="true" />}
            />
            <StatCard
              label="Jobs fallidos (30d)"
              value={stats.failed_jobs_30d}
              toneClass="text-error"
              icon={<AlertCircle size={18} aria-hidden="true" />}
            />
          </>
        ) : null}
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">Top canciones públicas</h2>

        <div className="overflow-x-auto rounded-xl border border-border bg-card">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="bg-card-hover text-xs font-semibold uppercase tracking-wider text-muted">
                <th className="w-12 px-4 py-3 text-left">#</th>
                <th className="px-4 py-3 text-left">Título</th>
                <th className="px-4 py-3 text-left">Etiquetas</th>
                <th className="px-4 py-3 text-left">Reproducciones</th>
                <th className="px-4 py-3 text-left">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-t border-border">
                    <td colSpan={5} className="px-4 py-3.5">
                      <div className="h-4 animate-pulse rounded bg-card-hover" />
                    </td>
                  </tr>
                ))
              ) : topSongs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-sm text-muted">
                    Sin canciones públicas todavía.
                  </td>
                </tr>
              ) : (
                topSongs.map((song, idx) => (
                  <tr
                    key={song.id}
                    className="border-t border-border transition-colors hover:bg-card-hover/60"
                  >
                    <td className="px-4 py-3 text-xs tabular-nums text-muted">{idx + 1}</td>
                    <td className="px-4 py-3 font-medium text-white">{song.title ?? '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(song.tags ?? []).slice(0, 3).map((t) => (
                          <Badge key={t.id} variant="primary">
                            {t.name}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-semibold tabular-nums text-white">
                      {(song.play_count ?? 0).toLocaleString('es-ES')}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted">
                      {new Date(song.created_at).toLocaleDateString('es-ES', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                      })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
