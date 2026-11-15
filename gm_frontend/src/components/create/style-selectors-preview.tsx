import { useEffect, useRef, useState } from 'react'
import styles from './style-selectors-preview.module.css'

interface SelectorConfig {
  id: string
  label: string
  placeholder: string
  options: string[]
}

interface StyleSelectorsPreviewProps {
  selected: Record<string, string[]>
  onChange: (selectorId: string, selected: string[]) => void
  disabled?: boolean
}

export interface ConfigurationOption {
  value: string
  label: string
}

interface ConfigurationSelectProps {
  label: string
  value: string
  options: ConfigurationOption[]
  onChange: (value: string) => void
  disabled?: boolean
  showLabel?: boolean
}

const SELECTORS: SelectorConfig[] = [
  {
    id: 'genres',
    label: 'Géneros',
    placeholder: 'Seleccionar género',
    options: ['Pop', 'Rock', 'Lofi', 'Jazz', 'Reggaetón', 'Salsa'],
  },
  {
    id: 'moods',
    label: 'Mood',
    placeholder: 'Seleccionar mood',
    options: ['Chill', 'Melancólico', 'Feliz', 'Energético', 'Romántico', 'Oscuro'],
  },
  {
    id: 'tempo',
    label: 'Tempo',
    placeholder: 'Seleccionar tempo',
    options: ['Lento', 'Medio', 'Rápido'],
  },
]

function MockMultiSelect({
  selector,
  selected,
  onChange,
  disabled = false,
}: {
  selector: SelectorConfig
  selected: string[]
  onChange: (selected: string[]) => void
  disabled?: boolean
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  const filteredOptions = selector.options.filter((option) =>
    option.toLowerCase().includes(query.toLowerCase())
  )

  function toggleOption(option: string) {
    onChange(
      selected.includes(option) ? selected.filter((item) => item !== option) : [...selected, option]
    )
    setQuery('')
  }

  function removeOption(option: string) {
    onChange(selected.filter((item) => item !== option))
  }

  return (
    <div ref={rootRef} className={styles.field}>
      <span className={styles.label}>{selector.label}</span>
      <div
        className={`${styles.select} ${open ? styles.selectOpen : ''}`}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => !disabled && setOpen(true)}
      >
        <div className={styles.valueArea}>
          {selected.map((option) => (
            <span key={option} className={styles.chip}>
              {option}
              <button
                type="button"
                aria-label={`Quitar ${option}`}
                className={styles.chipRemove}
                disabled={disabled}
                onClick={(event) => {
                  event.stopPropagation()
                  removeOption(option)
                }}
              >
                ×
              </button>
            </span>
          ))}
          <input
            disabled={disabled}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
              setOpen(true)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && filteredOptions[0]) {
                event.preventDefault()
                toggleOption(filteredOptions[0])
              }
              if (event.key === 'Escape') {
                setOpen(false)
              }
            }}
            placeholder={selected.length ? 'Añadir...' : selector.placeholder}
            className={styles.chipsInput}
            aria-label={`Buscar en ${selector.label}`}
          />
        </div>
      </div>

      {open && (
        <div className={styles.dropdown} role="listbox" aria-label={selector.label}>
          {filteredOptions.length > 0 ? (
            filteredOptions.map((option) => {
              const isSelected = selected.includes(option)
              return (
                <button
                  key={option}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`${styles.option} ${isSelected ? styles.optionSelected : ''}`}
                  disabled={disabled}
                  onClick={() => toggleOption(option)}
                >
                  <span>{option}</span>
                  {isSelected && <span aria-hidden="true">✓</span>}
                </button>
              )
            })
          ) : (
            <span className={styles.empty}>Sin resultados</span>
          )}
        </div>
      )}
    </div>
  )
}

export function ConfigurationSelect({
  label,
  value,
  options,
  onChange,
  disabled = false,
  showLabel = true,
}: ConfigurationSelectProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const selectedOption = options.find((option) => option.value === value)

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  return (
    <div ref={rootRef} className={`${styles.field} ${!showLabel ? styles.fieldCompact : ''}`}>
      {showLabel && <span className={styles.label}>{label}</span>}
      <div
        className={`${styles.select} ${open ? styles.selectOpen : ''}`}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={label}
        aria-disabled={disabled}
        onClick={() => !disabled && setOpen(true)}
      >
        <span className={styles.singleValue}>{selectedOption?.label ?? 'Seleccionar'}</span>
      </div>

      {open && (
        <div className={styles.dropdown} role="listbox" aria-label={label}>
          {options.map((option) => {
            const isSelected = option.value === value
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={isSelected}
                className={`${styles.option} ${isSelected ? styles.optionSelected : ''}`}
                disabled={disabled}
                onClick={() => {
                  onChange(option.value)
                  setOpen(false)
                }}
              >
                <span>{option.label}</span>
                {isSelected && <span aria-hidden="true">✓</span>}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function StyleSelectorsPreview({
  selected,
  onChange,
  disabled = false,
}: StyleSelectorsPreviewProps) {
  return (
    <div className={styles.selectors} aria-label="Selectores de estilo de prueba">
      {SELECTORS.map((selector) => (
        <MockMultiSelect
          key={selector.id}
          selector={selector}
          selected={selected[selector.id] ?? []}
          onChange={(values) => onChange(selector.id, values)}
          disabled={disabled}
        />
      ))}
    </div>
  )
}
