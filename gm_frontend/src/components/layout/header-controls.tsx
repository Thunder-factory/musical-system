import { useNavigate } from 'react-router-dom'
import { Bell, BellOff, BellRing, LoaderCircle } from 'lucide-react'

import { cn } from '../../lib/cn'
import { isPushConfigured } from '../../lib/env'
import { useActiveJobsStore } from '../../store/active-jobs.store'
import { DropdownMenu } from '../ui'

export type PushStatus = 'checking' | 'default' | 'granted' | 'registered' | 'denied' | 'unsupported'

export function ActiveJobsPill() {
  const navigate = useNavigate()
  const jobs = useActiveJobsStore((state) => state.jobs)

  if (jobs.length === 0) {
    return null
  }

  const hasRunning = jobs.some((j) => j.status === 'queued' || j.status === 'processing')

  if (jobs.length === 1) {
    const [job] = jobs
    return (
      <button
        type="button"
        onClick={() => navigate(job.route)}
        title={job.label}
        className="flex items-center gap-1.5 rounded-full border border-primary-border bg-primary-soft px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/20"
      >
        {hasRunning && <LoaderCircle size={13} className="animate-spin shrink-0" aria-hidden="true" />}
        <span className="hidden max-w-[140px] truncate sm:inline">{job.label}</span>
        {job.progressPct !== undefined && <span>{job.progressPct}%</span>}
      </button>
    )
  }

  return (
    <DropdownMenu
      align="right"
      triggerClassName="gap-1.5 rounded-full border border-primary-border bg-primary-soft px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/20"
      trigger={
        <>
          {hasRunning && <LoaderCircle size={13} className="animate-spin shrink-0" aria-hidden="true" />}
          <span>{jobs.length} procesos</span>
        </>
      }
      items={jobs.map((job) => ({
        id: job.id,
        label: job.progressPct !== undefined ? `${job.label} (${job.progressPct}%)` : job.label,
        onClick: () => navigate(job.route),
      }))}
    />
  )
}

interface PushButtonProps {
  status: PushStatus
  enabling: boolean
  onEnable: () => void
}

export function PushToggleButton({ status, enabling, onEnable }: PushButtonProps) {
  if (!isPushConfigured()) {
    return null
  }

  const label =
    status === 'registered'
      ? 'Activadas'
      : status === 'granted'
        ? 'Reintentar registro'
      : status === 'denied'
        ? 'Bloqueadas'
        : status === 'unsupported'
          ? 'No disponibles'
          : 'Activar'

  return (
    <button
      type="button"
      onClick={onEnable}
      disabled={enabling || status === 'checking' || status === 'denied' || status === 'unsupported'}
      aria-label={
        status === 'registered' ? 'Notificaciones push activadas' : 'Registrar notificaciones push'
      }
      className={cn(
        'hidden h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition-colors disabled:cursor-default sm:inline-flex',
        (status === 'granted' || status === 'registered') && 'bg-success-soft text-success',
        status === 'denied' && 'bg-error-soft text-error',
        (status === 'unsupported' || status === 'checking') && 'bg-card-hover text-muted',
        status === 'default' && 'bg-card-hover text-warning hover:bg-border-strong'
      )}
    >
      {enabling || status === 'checking' ? (
        <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
      ) : status === 'registered' ? (
        <BellRing size={14} aria-hidden="true" />
      ) : status === 'denied' || status === 'unsupported' ? (
        <BellOff size={14} aria-hidden="true" />
      ) : (
        <Bell size={14} aria-hidden="true" />
      )}
      <span className="hidden md:inline">{label}</span>
    </button>
  )
}
