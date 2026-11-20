import type { CommunityStats } from '../api/community.api'

export default function CommunityStatsRow({ stats }: { stats: CommunityStats | null }) {
  const cards = [
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
  ]

  return (
    <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
      {cards.map(({ label, value }) => (
        <div key={label} className="rounded-2xl border border-card-hover bg-card p-5">
          <span className="text-xs font-medium text-muted">{label}</span>
          <h2 className="mt-1.5 text-3xl font-black tabular-nums text-white">{value}</h2>
        </div>
      ))}
    </div>
  )
}
