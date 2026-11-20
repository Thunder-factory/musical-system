import type { ReactNode } from 'react'
import { Clapperboard, Upload } from 'lucide-react'

import { cn } from '../../../lib/cn'
import type { FaceSwapSourceMode } from '../types/faceswap.types'

interface Props {
  mode: FaceSwapSourceMode
  onModeChange: (mode: FaceSwapSourceMode) => void
  disabled?: boolean
  children: ReactNode
}

const TABS: { mode: FaceSwapSourceMode; label: string; icon: ReactNode }[] = [
  { mode: 'catalog', label: 'Catálogo', icon: <Clapperboard size={15} aria-hidden="true" /> },
  { mode: 'own', label: 'Mi clip', icon: <Upload size={15} aria-hidden="true" /> },
]

export default function SourceTabs({ mode, onModeChange, disabled = false, children }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <div
        role="tablist"
        aria-label="Fuente del video"
        className="inline-flex w-fit rounded-full bg-card-hover p-1"
      >
        {TABS.map((tab) => {
          const active = tab.mode === mode
          return (
            <button
              key={tab.mode}
              type="button"
              role="tab"
              id={`faceswap-tab-${tab.mode}`}
              aria-selected={active}
              aria-controls="faceswap-source-panel"
              disabled={disabled}
              onClick={() => onModeChange(tab.mode)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm transition-colors disabled:opacity-60',
                active ? 'bg-surface font-bold text-white' : 'text-muted hover:text-white'
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id="faceswap-source-panel" aria-labelledby={`faceswap-tab-${mode}`}>
        {children}
      </div>
    </div>
  )
}
