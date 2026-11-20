import { Check, Download, LoaderCircle, Pause, Play } from 'lucide-react'

import { Badge, Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { HummingJob, HummingVersion } from '../api/humming.api'
import { styleLabel } from '../lib/humming-constants'
import SimilarityBadge from './similarity-badge'

interface HummingVersionCardProps {
  job: HummingJob
  version: HummingVersion
  playing: boolean
  choosing: boolean
  onPlay: () => void
  onChoose: () => void
}

export function HummingVersionCard({
  job,
  version,
  playing,
  choosing,
  onPlay,
  onChoose,
}: HummingVersionCardProps) {
  const chosen = job.chosen_version === version.number
  const ai = version.ai
  const aiPending = Boolean(ai && (ai.status === 'queued' || ai.status === 'processing'))
  const aiFailed = ai?.status === 'failed'
  const locked = (job.chosen_version !== null && !chosen) || job.status !== 'completed' || aiPending

  return (
    <article
      className={cn(
        'flex flex-col gap-3 rounded-xl border bg-card-hover p-4',
        chosen ? 'border-primary' : 'border-transparent'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-3">
          {ai?.cover_url && (
            <img src={ai.cover_url} alt="" className="h-10 w-10 shrink-0 rounded-md object-cover" />
          )}
          <div className="min-w-0">
            <h3 className="font-semibold text-white">{styleLabel(version.style)}</h3>
            <p className="text-xs text-muted">
              Versión {version.number}
              {ai?.status === 'completed' && ' · producida con IA'}
            </p>
            {ai?.status === 'completed' && ai.similarity && (
              <SimilarityBadge similarity={ai.similarity} />
            )}
          </div>
        </div>
        {version.number === 1 && <Badge variant="primary">Principal</Badge>}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPlay}
          disabled={aiPending}
          aria-label={
            playing
              ? `Pausar ${styleLabel(version.style)}`
              : `Escuchar ${styleLabel(version.style)}`
          }
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-black transition-transform hover:scale-105 disabled:cursor-wait disabled:opacity-60"
        >
          {aiPending ? (
            <LoaderCircle size={18} className="animate-spin" aria-hidden="true" />
          ) : playing ? (
            <Pause size={18} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={18} fill="currentColor" aria-hidden="true" />
          )}
        </button>

        {aiPending ? (
          <span className="text-xs text-muted">Mejorando con IA…</span>
        ) : chosen ? (
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-success">
            <Check size={16} aria-hidden="true" /> En tu biblioteca
          </span>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            onClick={onChoose}
            loading={choosing}
            disabled={locked}
            title={
              job.status !== 'completed'
                ? 'Podrás elegir cuando terminen todas las versiones'
                : undefined
            }
            leftIcon={<Check size={14} aria-hidden="true" />}
          >
            Elegir
          </Button>
        )}

        {version.midi_url && (
          <a
            href={version.midi_url}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-xs text-muted hover:text-white"
            title="Descargar MIDI"
          >
            <Download size={14} aria-hidden="true" /> MIDI
          </a>
        )}
      </div>

      {aiFailed && (
        <p className="text-xs text-muted">
          No se pudo producir con IA; se usa la versión original.
        </p>
      )}
    </article>
  )
}
