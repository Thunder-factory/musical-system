import { useEffect, useState } from 'react'

import { Badge } from '../../../components/ui'
import type { MixClip } from '../api/mix.api'

type TimeField = 'start_time_ms' | 'end_time_ms' | 'fade_in_ms' | 'fade_out_ms'
export type ClipField = TimeField | 'volume'

interface ClipInspectorProps {
  clip: MixClip
  onUpdate: (field: ClipField, value: number) => Promise<void>
}

const secondsValue = (ms: number) => (ms / 1000).toFixed(2)

function clampTime(value: number, min: number, max?: number) {
  const bounded = Math.max(value, min)
  return max === undefined ? bounded : Math.min(bounded, max)
}

const NUMBER_INPUT_CLS =
  'w-full rounded-md border border-border bg-card-hover px-2.5 py-2 text-xs text-white outline-none focus:border-primary disabled:opacity-50'

export default function ClipInspector({ clip, onUpdate }: ClipInspectorProps) {
  const title = clip.custom_audio_name ?? clip.song_detail?.title ?? `Clip #${clip.position + 1}`
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
  }, [clip.id, clip.start_time_ms, clip.end_time_ms, clip.fade_in_ms, clip.fade_out_ms, clip.volume])

  async function commit(field: ClipField, value: number, rollback: string) {
    setSavingField(field)
    setError(null)
    try {
      await onUpdate(field, value)
    } catch {
      if (field === 'volume') {
        setVolumeDraft(Number(rollback))
      } else {
        setDrafts((cur) => ({ ...cur, [field]: rollback }))
      }
      setError('No se pudo guardar el cambio. Se restauró el valor anterior.')
    } finally {
      setSavingField(null)
    }
  }

  async function commitTime(field: TimeField) {
    const parsed = Number(drafts[field])
    if (!Number.isFinite(parsed)) {
      setDrafts((cur) => ({ ...cur, [field]: secondsValue(clip[field]) }))
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
    const ms = Math.round(seconds * 1000)
    setDrafts((cur) => ({ ...cur, [field]: secondsValue(ms) }))
    if (ms !== clip[field]) {
      await commit(field, ms, secondsValue(clip[field]))
    }
  }

  function setDraft(field: TimeField, value: string) {
    setDrafts((cur) => ({ ...cur, [field]: value }))
    setError(null)
  }

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex items-center justify-between gap-2">
        <strong className="truncate text-sm text-white" title={title}>
          {title}
        </strong>
        {clip.is_external && <Badge variant="primary">Archivo externo</Badge>}
      </div>

      <section className="rounded-lg border border-border bg-surface p-2.5">
        <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">
          Corte de audio
        </p>
        <div className="grid grid-cols-2 gap-2.5">
          {(
            [
              ['start_time_ms', 'Inicio (s)'],
              ['end_time_ms', 'Fin (s)'],
            ] as const
          ).map(([field, label]) => (
            <label key={field} className="flex flex-col gap-1 text-xs">
              <span className="text-muted">{label}</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={drafts[field]}
                disabled={savingField !== null}
                onChange={(e) => setDraft(field, e.target.value)}
                onBlur={() => void commitTime(field)}
                onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                className={NUMBER_INPUT_CLS}
              />
            </label>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-2 gap-2.5">
        {(
          [
            ['fade_in_ms', 'Entrada suave'],
            ['fade_out_ms', 'Salida suave'],
          ] as const
        ).map(([field, label]) => (
          <label key={field} className="flex flex-col gap-1 text-xs">
            <span className="text-muted">{label} (s)</span>
            <input
              type="number"
              min="0"
              max="5"
              step="0.01"
              value={drafts[field]}
              disabled={savingField !== null}
              onChange={(e) => setDraft(field, e.target.value)}
              onBlur={() => void commitTime(field)}
              onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
              aria-label={`${label} en segundos`}
              className={NUMBER_INPUT_CLS}
            />
          </label>
        ))}
      </div>

      <label className="flex flex-col gap-1.5 text-xs">
        <span className="text-muted">Volumen</span>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={0}
            max={2}
            step={0.05}
            value={volumeDraft}
            disabled={savingField !== null}
            onChange={(e) => {
              setVolumeDraft(Number(e.target.value))
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
            className="flex-1 accent-primary"
          />
          <span className="min-w-[40px] text-right tabular-nums text-muted">
            {Math.round(volumeDraft * 100)}%
          </span>
        </div>
      </label>

      {error && (
        <p role="alert" className="text-xs text-error">
          {error}
        </p>
      )}
    </div>
  )
}
