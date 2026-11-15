import { useEffect, useState } from 'react'
import type { MixClip } from '../../api/modules/mix.api'

type TimeField = 'start_time_ms' | 'end_time_ms' | 'fade_in_ms' | 'fade_out_ms'
export type ClipField = TimeField | 'volume'

interface ClipInspectorProps {
  clip: MixClip
  onUpdate: (field: ClipField, value: number) => Promise<void>
}

function secondsValue(milliseconds: number) {
  return (milliseconds / 1000).toFixed(2)
}

function clampTime(value: number, min: number, max?: number) {
  const bounded = Math.max(value, min)
  return max === undefined ? bounded : Math.min(bounded, max)
}

export default function ClipInspector({ clip, onUpdate }: ClipInspectorProps) {
  const [drafts, setDrafts] = useState({
    start_time_ms: secondsValue(clip.start_time_ms),
    end_time_ms: secondsValue(clip.end_time_ms),
    fade_in_ms: secondsValue(clip.fade_in_ms),
    fade_out_ms: secondsValue(clip.fade_out_ms),
  })
  const [savingField, setSavingField] = useState<ClipField | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [volumeDraft, setVolumeDraft] = useState(clip.volume)

  useEffect(() => {
    setDrafts({
      start_time_ms: secondsValue(clip.start_time_ms),
      end_time_ms: secondsValue(clip.end_time_ms),
      fade_in_ms: secondsValue(clip.fade_in_ms),
      fade_out_ms: secondsValue(clip.fade_out_ms),
    })
    setVolumeDraft(clip.volume)
    setError(null)
  }, [
    clip.id,
    clip.start_time_ms,
    clip.end_time_ms,
    clip.fade_in_ms,
    clip.fade_out_ms,
    clip.volume,
  ])

  async function commitTime(field: TimeField) {
    const parsed = Number(drafts[field])
    if (!Number.isFinite(parsed)) {
      setDrafts((current) => ({ ...current, [field]: secondsValue(clip[field]) }))
      return
    }

    const maxSeconds = clip.duration_ms / 1000
    let seconds = Math.max(parsed, 0)
    if (field === 'start_time_ms') {
      seconds = clampTime(seconds, 0, Math.max(0, clip.end_time_ms / 1000 - 0.1))
    } else if (field === 'end_time_ms') {
      seconds = clampTime(seconds, clip.start_time_ms / 1000 + 0.1, maxSeconds)
    } else {
      seconds = clampTime(seconds, 0, 5)
    }

    const milliseconds = Math.round(seconds * 1000)
    setDrafts((current) => ({ ...current, [field]: secondsValue(milliseconds) }))
    if (milliseconds === clip[field]) {
      return
    }
    await commit(field, milliseconds, secondsValue(clip[field]))
  }

  async function commit(field: ClipField, value: number, rollback: string) {
    setSavingField(field)
    setError(null)
    try {
      await onUpdate(field, value)
    } catch {
      if (field === 'volume') {
        setVolumeDraft(Number(rollback))
      } else {
        setDrafts((current) => ({ ...current, [field]: rollback }))
      }
      setError('No se pudo guardar el cambio. Se restauró el valor anterior.')
    } finally {
      setSavingField(null)
    }
  }

  function setDraft(field: TimeField, value: string) {
    setDrafts((current) => ({ ...current, [field]: value }))
    setError(null)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <section
        style={{
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: 10,
          background: 'var(--bg-surface)',
        }}
      >
        <p
          style={{
            margin: '0 0 8px',
            fontSize: 11,
            color: 'var(--text-subdued)',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          Corte de audio
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {(
            [
              ['start_time_ms', 'Inicio (s)'],
              ['end_time_ms', 'Fin (s)'],
            ] as const
          ).map(([field, label]) => (
            <label
              key={field}
              style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}
            >
              <span style={{ color: 'var(--text-subdued)' }}>{label}</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={drafts[field]}
                disabled={savingField !== null}
                onChange={(event) => setDraft(field, event.target.value)}
                onBlur={() => void commitTime(field)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.currentTarget.blur()
                  }
                }}
                style={inputStyle}
              />
            </label>
          ))}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <TimeInput
          label="Fade in"
          field="fade_in_ms"
          value={drafts.fade_in_ms}
          disabled={savingField !== null}
          onChange={(value) => setDraft('fade_in_ms', value)}
          onCommit={() => void commitTime('fade_in_ms')}
        />
        <TimeInput
          label="Fade out"
          field="fade_out_ms"
          value={drafts.fade_out_ms}
          disabled={savingField !== null}
          onChange={(value) => setDraft('fade_out_ms', value)}
          onCommit={() => void commitTime('fade_out_ms')}
        />
      </div>

      <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
        <span style={{ color: 'var(--text-subdued)' }}>Volumen</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="range"
            min={0}
            max={2}
            step={0.05}
            value={volumeDraft}
            disabled={savingField !== null}
            onChange={(event) => {
              setVolumeDraft(Number(event.target.value))
              setError(null)
            }}
            onMouseUp={() => {
              if (volumeDraft !== clip.volume) {
                void commit('volume', volumeDraft, String(clip.volume))
              }
            }}
            onBlur={() => {
              if (volumeDraft !== clip.volume) {
                void commit('volume', volumeDraft, String(clip.volume))
              }
            }}
            style={{ flex: 1, accentColor: 'var(--color-primary)' }}
          />
          <span style={{ minWidth: 40, color: 'var(--text-subdued)', textAlign: 'right' }}>
            {Math.round(volumeDraft * 100)}%
          </span>
        </div>
      </label>

      {error && (
        <p role="alert" style={{ margin: 0, color: 'var(--color-error)', fontSize: 12 }}>
          {error}
        </p>
      )}
    </div>
  )
}

function TimeInput({
  label,
  field,
  value,
  disabled,
  onChange,
  onCommit,
}: {
  label: string
  field: TimeField
  value: string
  disabled: boolean
  onChange: (value: string) => void
  onCommit: () => void
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12 }}>
      <span style={{ color: 'var(--text-subdued)' }}>{label} (s)</span>
      <input
        type="number"
        min="0"
        max="5"
        step="0.01"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onCommit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.currentTarget.blur()
          }
        }}
        style={inputStyle}
        aria-label={`${label} en segundos`}
        data-field={field}
      />
    </label>
  )
}

const inputStyle = {
  width: '100%',
  boxSizing: 'border-box' as const,
  padding: '8px 10px',
  borderRadius: 6,
  border: '1px solid var(--border)',
  background: 'var(--bg-card-hover)',
  color: 'var(--text-base)',
  fontSize: 13,
  outline: 'none',
}
