import { LoaderCircle } from 'lucide-react'

import type { HummingJob } from '../api/humming.api'
import { STAGE_LABELS } from '../lib/humming-constants'

export function HummingInitialProgress({ job }: { job: HummingJob }) {
  const label = STAGE_LABELS[job.stage] ?? (job.status === 'queued' ? 'En cola…' : 'Procesando…')
  return (
    <div className="flex flex-col gap-3" aria-live="polite">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-2 text-sm font-medium text-white">
          <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
          {label}
        </span>
        <span className="text-xs tabular-nums text-muted">{job.progress}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-card-hover">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${job.progress}%` }}
        />
      </div>
      <p className="text-xs text-muted">Suele tardar menos de un minuto.</p>
    </div>
  )
}

export function HummingAiProgress({ job }: { job: HummingJob }) {
  const conIa = job.versions.filter((v) => v.ai)
  const aiTotal = conIa.length
  const aiListas = conIa.filter(
    (v) => v.ai?.status === 'completed' || v.ai?.status === 'failed'
  ).length
  const aiWorking = conIa.some((v) => v.ai?.status === 'queued' || v.ai?.status === 'processing')
  const working = job.status === 'queued' || job.status === 'processing'

  if (!working && !aiWorking) {
    return null
  }

  const progresoTotal = aiTotal
    ? Math.round(job.progress / 2 + (50 * aiListas) / Math.max(aiTotal, job.versions.length))
    : job.progress

  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-2 text-sm font-medium text-white">
          <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
          {aiListas > 0
            ? 'Escucha las listas mientras producimos las demás con IA…'
            : 'Produciendo tus versiones con IA…'}
        </span>
        <span className="text-xs tabular-nums text-muted">
          {aiTotal > 0
            ? `${aiListas}/${Math.max(aiTotal, job.versions.length)} con IA`
            : `${job.progress}%`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-card-hover">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${progresoTotal}%` }}
        />
      </div>
    </div>
  )
}
