import { useId } from 'react'
import type { MouseEvent } from 'react'
import { Crosshair, Info, X } from 'lucide-react'

import { useFaceTargetVideo } from '../../hooks/useFaceTargetVideo'
import { formatClipDuration } from '../../types/faceswap.types'
import type { FaceTarget } from '../../types/faceswap.types'
import FaceTargetControls from './face-target-controls'
import { containBox, pointToFrame, round } from './face-target-geometry'
import { BTN_GHOST } from './faceswap-ui'

interface Props {
  /** preview_url de la plantilla u object URL del clip propio. */
  src: string
  value: FaceTarget | null
  onChange: (target: FaceTarget | null) => void
  disabled?: boolean
}

/** Paso 2b: pausar el video base y hacer clic sobre la cara del personaje a reemplazar. */
export default function FaceTargetPicker({ src, value, onChange, disabled = false }: Props) {
  const helpId = useId()
  const { videoRef, handlers, playing, time, duration, box, ready, ratio, toggle, seek } =
    useFaceTargetVideo()
  const atRef = value != null && Math.abs(time - value.ref_time_s) < 0.1

  function pick(e: MouseEvent<HTMLDivElement>) {
    const el = videoRef.current
    if (disabled || !el || !ready) {
      return
    }
    el.pause()
    const rect = e.currentTarget.getBoundingClientRect()
    const frame = containBox(rect.width, rect.height, el.videoWidth, el.videoHeight)
    const point = frame && pointToFrame(e.clientX - rect.left, e.clientY - rect.top, frame)
    if (!point) {
      return // clic en las bandas negras
    }
    onChange({ ref_time_s: round(el.currentTime, 2), face_x: point.x, face_y: point.y })
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className="relative max-h-[min(56vh,420px)] w-full overflow-hidden rounded-lg bg-black"
        style={{ aspectRatio: ratio ?? 16 / 9 }}
      >
        <video
          ref={videoRef}
          src={src}
          muted
          playsInline
          preload="auto"
          className="h-full w-full object-contain"
          {...handlers}
        />
        <div
          role="group"
          aria-label="Fotograma del video: haz clic sobre la cara del personaje"
          aria-describedby={helpId}
          onClick={pick}
          className={`absolute inset-0 ${disabled ? 'cursor-not-allowed' : 'cursor-crosshair'}`}
        >
          {value && box && (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute h-12 w-12 -translate-x-1/2 -translate-y-1/2 rounded-full transition-opacity"
              style={{
                left: box.left + value.face_x * box.width,
                top: box.top + value.face_y * box.height,
                border: '3px solid var(--color-primary)',
                boxShadow: '0 0 0 2px var(--overlay), 0 0 16px var(--color-primary)',
                opacity: atRef ? 1 : 0.45,
              }}
            />
          )}
        </div>
      </div>

      <FaceTargetControls
        playing={playing}
        time={time}
        duration={duration}
        onToggle={toggle}
        onSeek={seek}
        disabled={disabled}
      />

      {value ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-card-hover px-3 py-2">
          <button
            type="button"
            onClick={() => seek(value.ref_time_s)}
            aria-label={`Ir al momento elegido, ${formatClipDuration(value.ref_time_s)}`}
            className="inline-flex items-center gap-2 text-sm font-medium text-white hover:text-primary"
          >
            <Crosshair size={15} className="text-primary" aria-hidden="true" />
            Personaje elegido en {formatClipDuration(value.ref_time_s)}
          </button>
          <button
            type="button"
            className={BTN_GHOST}
            disabled={disabled}
            onClick={() => onChange(null)}
            aria-label="Quitar selección del personaje"
          >
            <X size={13} aria-hidden="true" />
            Quitar selección
          </button>
        </div>
      ) : null}
      <p id={helpId} className="flex items-start gap-1.5 text-xs text-muted">
        <Info size={13} className="mt-px shrink-0" aria-hidden="true" />
        Pausa donde se vea bien la cara y haz clic sobre ella. Si no eliges, se cambiará la cara
        principal.
      </p>
    </div>
  )
}
