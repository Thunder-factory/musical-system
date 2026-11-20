import { useState } from 'react'

import type { StemFile } from '../api/stems.api'
import StemTrackRow from './stem-track-row'

interface StemResultCardProps {
  stemFiles: StemFile[]
  sourceFilename?: string
  createdAt?: string
}

export default function StemResultCard({
  stemFiles,
  sourceFilename,
  createdAt,
}: StemResultCardProps) {
  const [activeStemId, setActiveStemId] = useState<string | null>(null)

  if (stemFiles.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-xl border border-primary-border bg-card-hover px-4 py-3">
        <p className="text-xs text-muted">Resultado de separación</p>
        <p className="truncate text-sm font-semibold text-white" title={sourceFilename}>
          {sourceFilename ?? 'Archivo de audio'}
        </p>
        <p className="mt-1 text-xs text-muted">
          {createdAt ? new Date(createdAt).toLocaleString() : 'Pistas disponibles'} ·{' '}
          {stemFiles.length} pistas
        </p>
      </div>
      {stemFiles.map((stemFile) => (
        <StemTrackRow
          key={stemFile.id}
          stemFile={stemFile}
          active={activeStemId === stemFile.id}
          onActivate={() => setActiveStemId(stemFile.id)}
        />
      ))}
    </div>
  )
}
