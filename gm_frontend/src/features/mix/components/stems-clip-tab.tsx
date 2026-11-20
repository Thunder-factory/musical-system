import { AudioWaveform, Plus } from 'lucide-react'

import { EmptyState } from '../../../components/ui'
import type { StemJob } from '../../stems/api/stems.api'

interface StemsClipTabProps {
  stemJobs: StemJob[]
  adding: boolean
  onSelectStem: (stemFileId: string, durationMs?: number) => void
}

const STEM_LABELS: Record<string, string> = {
  vocals: 'Voces',
  no_vocals: 'Instrumental',
  drums: 'Batería',
  bass: 'Bajo',
  other: 'Otros',
}

export default function StemsClipTab({ stemJobs, adding, onSelectStem }: StemsClipTabProps) {
  const readyStems = stemJobs
    .filter((j) => j.status === 'completed' && j.stem_files && j.stem_files.length > 0)
    .flatMap((j) => j.stem_files!.map((sf) => ({ job: j, sf })))

  if (readyStems.length === 0) {
    return (
      <div className="p-4">
        <EmptyState
          icon={<AudioWaveform size={22} />}
          title="Sin pistas separadas"
          description="Separa las pistas de una canción en el estudio para usarlas de forma independiente."
          actionLabel="Ir a Separar pistas"
          actionTo="/stems"
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col py-1">
      {readyStems.map(({ job, sf }) => (
        <button
          key={sf.id}
          type="button"
          disabled={adding}
          onClick={() =>
            !adding &&
            onSelectStem(
              sf.id,
              sf.duration_seconds ? Math.round(sf.duration_seconds * 1000) : undefined
            )
          }
          className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-card-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-success-soft text-[10px] font-bold uppercase text-success">
            {(STEM_LABELS[sf.stem_type] ?? sf.stem_type).slice(0, 4)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">
              {STEM_LABELS[sf.stem_type] ?? sf.stem_type.replace('_', ' ')}
            </p>
            <p className="truncate text-xs text-muted">{job.source_filename}</p>
          </div>
          <Plus size={15} className="shrink-0 text-muted" aria-hidden="true" />
        </button>
      ))}
    </div>
  )
}
