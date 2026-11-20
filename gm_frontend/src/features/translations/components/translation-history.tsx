import { Languages } from 'lucide-react'

import { Badge, EmptyState, type BadgeVariant } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { TranslationJob } from '../api/translations.api'
import { LANGUAGE_NAMES, TRANSLATION_STATUS_LABELS } from '../lib/translation-constants'

const STATUS_VARIANTS: Record<string, BadgeVariant> = {
  queued: 'warning',
  processing: 'warning',
  completed: 'success',
  failed: 'error',
}

interface TranslationHistoryProps {
  history: TranslationJob[]
  activeJobId: string | null
  onSelect: (id: string) => void
}

export default function TranslationHistory({
  history,
  activeJobId,
  onSelect,
}: TranslationHistoryProps) {
  return (
    <section className="flex min-w-0 flex-col gap-3" aria-label="Historial de traducciones">
      <h2 className="text-sm font-semibold text-white">Historial de traducciones</h2>

      {history.length === 0 ? (
        <EmptyState
          icon={<Languages size={20} aria-hidden="true" />}
          title="Sin traducciones todavía"
          description="Sube un video musical arriba para doblarlo a otro idioma."
          className="py-6"
        />
      ) : (
        <div className="flex max-h-[480px] flex-col gap-2.5 overflow-y-auto">
          {history.map((item) => {
            const selected = item.id === activeJobId
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect(item.id)}
                className={cn(
                  'flex w-full items-center justify-between gap-3 rounded-xl border bg-card-hover px-4 py-3 text-left transition-colors',
                  selected ? 'border-primary' : 'border-transparent hover:border-border-strong'
                )}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">
                    {item.song_title || item.source_filename}
                  </p>
                  <p className="text-xs text-muted">
                    → {LANGUAGE_NAMES[item.target_language] ?? item.target_language} ·{' '}
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>
                <Badge variant={STATUS_VARIANTS[item.status] ?? 'neutral'}>
                  {TRANSLATION_STATUS_LABELS[item.status] ?? item.status}
                  {['queued', 'processing'].includes(item.status) ? ` · ${item.progress_pct}%` : ''}
                </Badge>
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
