import type { ReactNode } from 'react'
import { AlignLeft, PenLine, Sparkles } from 'lucide-react'

import { cn } from '../../../lib/cn'
import { CREATE_MODE_META, type CreateMode } from '../lib/create-song-options'

const MODE_ICONS: Record<CreateMode, ReactNode> = {
  description: <Sparkles size={15} aria-hidden="true" />,
  exact_lyrics: <AlignLeft size={15} aria-hidden="true" />,
  auto_lyrics: <PenLine size={15} aria-hidden="true" />,
}

interface CreateModeTabsProps {
  mode: CreateMode
  disabled?: boolean
  onChange: (mode: CreateMode) => void
}

export function CreateModeTabs({ mode, disabled = false, onChange }: CreateModeTabsProps) {
  const activeMode = CREATE_MODE_META.find((item) => item.id === mode)

  return (
    <div className="flex flex-col gap-2">
      <div
        role="tablist"
        aria-label="Modo de creación"
        className="grid grid-cols-1 gap-1.5 rounded-xl bg-card-hover p-1.5 sm:grid-cols-3"
      >
        {CREATE_MODE_META.map((item) => {
          const active = item.id === mode
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={active}
              disabled={disabled}
              onClick={() => onChange(item.id)}
              className={cn(
                'flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                active ? 'bg-surface text-primary shadow-sm' : 'text-muted hover:text-white'
              )}
            >
              {MODE_ICONS[item.id]}
              <span>{item.label}</span>
            </button>
          )
        })}
      </div>
      {activeMode && <p className="text-xs text-muted">{activeMode.hint}</p>}
    </div>
  )
}

export default CreateModeTabs
