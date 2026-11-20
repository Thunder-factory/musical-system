import { useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'

import { Input } from '../../../components/ui'

export interface TagOption {
  id: number
  slug: string
  label: string
}

const TAG_GROUPS: Array<{ key: string; label: string; tags: TagOption[] }> = [
  {
    key: 'genre',
    label: 'Género',
    tags: [
      { id: 1, slug: 'lofi', label: 'Lo-Fi' },
      { id: 2, slug: 'pop', label: 'Pop' },
      { id: 3, slug: 'reggaeton', label: 'Reggaetón' },
      { id: 4, slug: 'rock', label: 'Rock' },
      { id: 5, slug: 'bachata', label: 'Bachata' },
      { id: 6, slug: 'kpop', label: 'K-Pop' },
      { id: 7, slug: 'jazz', label: 'Jazz' },
      { id: 8, slug: 'cumbia', label: 'Cumbia' },
      { id: 9, slug: 'ranchera', label: 'Ranchera' },
      { id: 10, slug: 'techno', label: 'Techno' },
      { id: 11, slug: 'electronic', label: 'Electrónica' },
      { id: 12, slug: 'hip-hop', label: 'Hip-Hop' },
      { id: 13, slug: 'r&b', label: 'R&B' },
      { id: 14, slug: 'folk', label: 'Folk' },
      { id: 15, slug: 'salsa', label: 'Salsa' },
      { id: 16, slug: 'classical', label: 'Clásica' },
    ],
  },
  {
    key: 'mood',
    label: 'Ambiente',
    tags: [
      { id: 17, slug: 'chill', label: 'Relajado' },
      { id: 18, slug: 'sad', label: 'Triste' },
      { id: 19, slug: 'happy', label: 'Alegre' },
      { id: 20, slug: 'energetic', label: 'Enérgico' },
      { id: 21, slug: 'romantic', label: 'Romántico' },
      { id: 22, slug: 'melancholic', label: 'Melancólico' },
      { id: 23, slug: 'nostalgic', label: 'Nostálgico' },
      { id: 24, slug: 'dark', label: 'Oscuro' },
      { id: 25, slug: 'angry', label: 'Intenso' },
      { id: 26, slug: 'playful', label: 'Divertido' },
      { id: 27, slug: 'hopeful', label: 'Esperanzador' },
      { id: 28, slug: 'motivated', label: 'Motivado' },
    ],
  },
  {
    key: 'tempo',
    label: 'Ritmo',
    tags: [
      { id: 29, slug: 'slow', label: 'Lento' },
      { id: 30, slug: 'medium', label: 'Medio' },
      { id: 31, slug: 'fast', label: 'Rápido' },
    ],
  },
]

const MAX_COLLAPSED = 6

interface MixTagPickerProps {
  selectedIds: number[]
  onToggle: (id: number) => void
}

export default function MixTagPicker({ selectedIds, onToggle }: MixTagPickerProps) {
  const [query, setQuery] = useState('')
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({ genre: true })
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})

  const normalized = query.trim().toLowerCase()

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted">
          Etiquetas <span className="font-normal">(opcional)</span>
        </span>
        {selectedIds.length > 0 && (
          <span className="text-[11px] font-semibold text-primary">
            {selectedIds.length} seleccionada{selectedIds.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div className="relative">
        <Search
          size={14}
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
        />
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar género o ambiente..."
          aria-label="Buscar etiquetas"
          className="py-1.5 pl-8 text-xs"
        />
      </div>

      <div className="flex flex-col gap-2">
        {TAG_GROUPS.map((group) => {
          const matches = normalized
            ? group.tags.filter(
                (t) =>
                  t.label.toLowerCase().includes(normalized) ||
                  t.slug.toLowerCase().includes(normalized)
              )
            : group.tags
          if (matches.length === 0) {
            return null
          }

          const isOpen = normalized ? true : Boolean(openGroups[group.key])
          const isExpanded = normalized || Boolean(expandedGroups[group.key])
          const visible = isExpanded ? matches : matches.slice(0, MAX_COLLAPSED)
          const hasMore = !normalized && matches.length > MAX_COLLAPSED

          return (
            <div key={group.key} className="rounded-lg border border-border bg-surface p-2.5">
              <button
                type="button"
                onClick={() => setOpenGroups((prev) => ({ ...prev, [group.key]: !isOpen }))}
                aria-expanded={isOpen}
                className="flex w-full items-center justify-between text-left text-xs font-bold uppercase tracking-wider text-muted hover:text-white"
              >
                <span>{group.label}</span>
                <ChevronDown
                  size={14}
                  aria-hidden="true"
                  className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
              </button>

              {isOpen && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {visible.map((tag) => {
                    const active = selectedIds.includes(tag.id)
                    return (
                      <button
                        key={tag.id}
                        type="button"
                        onClick={() => onToggle(tag.id)}
                        aria-pressed={active}
                        className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                          active
                            ? 'border-primary bg-primary-soft font-semibold text-primary'
                            : 'border-border-strong bg-card-hover text-muted hover:text-white'
                        }`}
                      >
                        {tag.label}
                      </button>
                    )
                  })}
                  {hasMore && (
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedGroups((prev) => ({ ...prev, [group.key]: !isExpanded }))
                      }
                      className="rounded-full px-2.5 py-1 text-xs font-semibold text-primary hover:underline"
                    >
                      {isExpanded ? 'Ver menos' : `+${matches.length - MAX_COLLAPSED} más`}
                    </button>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
