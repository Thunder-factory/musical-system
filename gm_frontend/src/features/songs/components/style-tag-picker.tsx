import { cn } from '../../../lib/cn'

export type SelectedTagsMap = Record<'genres' | 'moods' | 'tempo', string[]>

interface TagGroupConfig {
  id: keyof SelectedTagsMap
  label: string
  options: string[]
}

const TAG_GROUPS: TagGroupConfig[] = [
  {
    id: 'genres',
    label: 'Género',
    options: ['Pop', 'Rock', 'Lofi', 'Jazz', 'Reggaetón', 'Salsa', 'Electrónica', 'Acústico'],
  },
  {
    id: 'moods',
    label: 'Ambiente',
    options: ['Chill', 'Melancólico', 'Feliz', 'Energético', 'Romántico', 'Oscuro'],
  },
  {
    id: 'tempo',
    label: 'Ritmo',
    options: ['Lento', 'Medio', 'Rápido'],
  },
]

interface StyleTagPickerProps {
  selected: SelectedTagsMap
  disabled?: boolean
  onChange: (group: keyof SelectedTagsMap, values: string[]) => void
}

export function StyleTagPicker({ selected, disabled = false, onChange }: StyleTagPickerProps) {
  function toggle(group: keyof SelectedTagsMap, option: string) {
    const current = selected[group]
    const next = current.includes(option)
      ? current.filter((item) => item !== option)
      : [...current, option]
    onChange(group, next)
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-3.5">
      {TAG_GROUPS.map((group) => (
        <div key={group.id} className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold text-muted">{group.label}</span>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label={group.label}>
            {group.options.map((option) => {
              const active = selected[group.id].includes(option)
              return (
                <button
                  key={option}
                  type="button"
                  disabled={disabled}
                  aria-pressed={active}
                  onClick={() => toggle(group.id, option)}
                  className={cn(
                    'rounded-full border px-3 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                    active
                      ? 'border-primary bg-primary-soft text-primary'
                      : 'border-border-strong bg-card text-muted hover:text-white'
                  )}
                >
                  {option}
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

export default StyleTagPicker
