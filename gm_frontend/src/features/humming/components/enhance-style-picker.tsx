import { Input } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { HummingFidelity, HummingStyle } from '../api/humming.api'
import { CUSTOM_HUMMING_STYLE, FIDELITY_LABELS } from '../lib/humming-constants'

interface EnhanceStylePickerProps {
  groups: [string, HummingStyle[]][]
  fidelities: HummingFidelity[]
  style: string
  customStyle: string
  fidelity: HummingFidelity
  onStyleChange: (value: string) => void
  onCustomStyleChange: (value: string) => void
  onFidelityChange: (value: HummingFidelity) => void
}

function chipClass(selected: boolean) {
  return cn(
    'rounded-full border px-3 py-1.5 text-xs font-medium transition-colors sm:text-sm',
    selected
      ? 'border-primary bg-primary text-black'
      : 'border-border-strong bg-card-hover text-white hover:border-primary'
  )
}

export default function EnhanceStylePicker({
  groups,
  fidelities,
  style,
  customStyle,
  fidelity,
  onStyleChange,
  onCustomStyleChange,
  onFidelityChange,
}: EnhanceStylePickerProps) {
  return (
    <div className="flex flex-col gap-4">
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 text-sm font-medium text-white">Estilo</legend>
        {groups.map(([group, styles]) => (
          <div key={group} className="flex flex-col gap-1.5">
            <span className="text-xs text-muted">
              {group}
              {styles.some((item) => item.experimental) && ' · experimental'}
            </span>
            <div className="flex flex-wrap gap-2">
              {styles.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => onStyleChange(item.key)}
                  aria-pressed={style === item.key}
                  className={chipClass(style === item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ))}

        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-muted">Otro</span>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => onStyleChange(CUSTOM_HUMMING_STYLE)}
              aria-pressed={style === CUSTOM_HUMMING_STYLE}
              className={chipClass(style === CUSTOM_HUMMING_STYLE)}
            >
              Describir mi estilo
            </button>
            {style === CUSTOM_HUMMING_STYLE && (
              <Input
                aria-label="Describe el estilo"
                value={customStyle}
                onChange={(event) => onCustomStyleChange(event.target.value)}
                maxLength={200}
                placeholder="Ej.: cumbia con sintetizadores y charango"
                className="min-w-[220px] flex-1"
              />
            )}
          </div>
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium text-white">Fidelidad a tu melodía</legend>
        <div className="flex flex-wrap gap-2">
          {fidelities.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => onFidelityChange(key)}
              aria-pressed={fidelity === key}
              className={chipClass(fidelity === key)}
            >
              {FIDELITY_LABELS[key]?.label ?? key}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted">{FIDELITY_LABELS[fidelity]?.hint}</p>
      </fieldset>
    </div>
  )
}
