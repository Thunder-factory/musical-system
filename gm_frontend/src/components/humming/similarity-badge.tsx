import { AudioLines } from 'lucide-react'

import type { HummingSimilarity } from '../../api/modules/humming.api'

const LEVEL_LABEL: Record<HummingSimilarity['nivel'], string> = {
  alto: 'alto',
  medio: 'medio',
  bajo: 'bajo',
}

export const SIMILARITY_EXPLANATION =
  'Qué parte de tu melodía se escucha en esta versión, descontando las coincidencias por azar. ' +
  'Las versiones con IA cambian instrumentos y arreglo, así que 40-50 % ya es muy fiel; ' +
  'una melodía distinta da menos de 10 %.'

/** "Parecido con tu melodía: 45 % · alto" (ver gm_tarareo/app/pipeline/parecido.py). */
export default function SimilarityBadge({
  similarity,
  compact = false,
}: {
  similarity: HummingSimilarity
  compact?: boolean
}) {
  const pct = Math.round(similarity.puntaje * 100)
  return (
    <span
      className="inline-flex items-center gap-1 text-xs"
      style={{ color: 'var(--text-base-soft)' }}
      title={SIMILARITY_EXPLANATION}
    >
      <AudioLines size={12} aria-hidden="true" />
      {compact
        ? `${pct} %`
        : `Parecido con tu melodía: ${pct} % · ${LEVEL_LABEL[similarity.nivel]}`}
    </span>
  )
}
