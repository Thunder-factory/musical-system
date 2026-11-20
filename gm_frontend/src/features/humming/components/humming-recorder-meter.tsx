import { LoaderCircle, Mic, Square } from 'lucide-react'

import { cn } from '../../../lib/cn'
import type { RecorderState } from '../hooks/useAudioRecorder'
import { formatSeconds, MAX_HUMMING_SECONDS, MIN_HUMMING_SECONDS } from '../lib/humming-constants'

interface HummingRecorderMeterProps {
  state: RecorderState
  elapsed: number
  disabled: boolean
  onRecordClick: () => void
}

export function HummingRecorderMeter({
  state,
  elapsed,
  disabled,
  onRecordClick,
}: HummingRecorderMeterProps) {
  const isRecording = state === 'recording'
  const progressPct = Math.min(100, (elapsed / MAX_HUMMING_SECONDS) * 100)

  return (
    <div className="flex items-center gap-5">
      <button
        type="button"
        onClick={onRecordClick}
        disabled={disabled || state === 'requesting'}
        aria-label={isRecording ? 'Detener grabación' : 'Empezar a grabar'}
        className={cn(
          'relative flex h-20 w-20 shrink-0 items-center justify-center rounded-full transition-transform hover:scale-105 disabled:cursor-not-allowed disabled:opacity-50',
          isRecording ? 'bg-error text-white' : 'bg-primary text-black'
        )}
      >
        {isRecording && (
          <span
            className="pointer-events-none absolute inset-0 animate-ping rounded-full bg-error/35"
            aria-hidden="true"
          />
        )}
        {state === 'requesting' ? (
          <LoaderCircle size={28} className="animate-spin" aria-hidden="true" />
        ) : isRecording ? (
          <Square size={24} fill="currentColor" aria-hidden="true" />
        ) : (
          <Mic size={30} aria-hidden="true" />
        )}
      </button>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h2 id="humming-recorder-title" className="text-lg font-semibold text-white">
          {isRecording ? 'Grabando… tararea tu melodía' : 'Graba tu tarareo'}
        </h2>
        <div className="relative h-2 overflow-hidden rounded-full bg-card-hover" aria-hidden="true">
          <div
            className="h-full rounded-full bg-primary transition-all duration-100"
            style={{ width: `${progressPct}%` }}
          />
          <div
            className="absolute inset-y-0 w-0.5 bg-white/40"
            style={{ left: `${(MIN_HUMMING_SECONDS / MAX_HUMMING_SECONDS) * 100}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted">
          <span aria-live="polite" className="tabular-nums">
            {formatSeconds(elapsed)} / {formatSeconds(MAX_HUMMING_SECONDS)}
          </span>
          <span>Mínimo {MIN_HUMMING_SECONDS} s · ideal 15–20 s</span>
        </div>
      </div>
    </div>
  )
}
