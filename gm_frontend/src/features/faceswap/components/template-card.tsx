import { useRef, useState } from 'react'
import { Check, Play } from 'lucide-react'

import { cn } from '../../../lib/cn'
import { formatClipDuration, type FaceSwapTemplate } from '../types/faceswap.types'

interface Props {
  template: FaceSwapTemplate
  selected: boolean
  onSelect: () => void
  disabled?: boolean
}

export default function TemplateCard({ template, selected, onSelect, disabled = false }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [hovering, setHovering] = useState(false)
  const [thumbFailed, setThumbFailed] = useState(false)

  function startPreview() {
    setHovering(true)
    void videoRef.current?.play().catch(() => undefined)
  }

  function stopPreview() {
    setHovering(false)
    const video = videoRef.current
    if (video) {
      video.pause()
      video.currentTime = 0
    }
  }

  return (
    <button
      type="button"
      onClick={onSelect}
      onMouseEnter={startPreview}
      onMouseLeave={stopPreview}
      onFocus={startPreview}
      onBlur={stopPreview}
      disabled={disabled}
      aria-pressed={selected}
      aria-label={`${template.title}, ${formatClipDuration(template.duration_seconds)}`}
      className={cn(
        'group flex min-w-0 flex-col gap-2 rounded-xl border-2 bg-card-hover p-1.5 text-left transition-all duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0',
        selected ? 'border-primary' : 'border-transparent'
      )}
    >
      <div className="relative aspect-[9/16] w-full overflow-hidden rounded-md bg-surface">
        {!thumbFailed && (
          <img
            src={template.thumbnail_url || undefined}
            alt=""
            loading="lazy"
            onError={() => setThumbFailed(true)}
            className="absolute inset-0 h-full w-full object-cover"
          />
        )}
        <video
          ref={videoRef}
          src={template.preview_url || undefined}
          muted
          loop
          playsInline
          preload="none"
          className={cn(
            'absolute inset-0 h-full w-full object-cover transition-opacity duration-300',
            hovering ? 'opacity-100' : 'opacity-0'
          )}
        />
        {!hovering && (
          <span className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity group-hover:opacity-100">
            <Play size={22} className="text-white" aria-hidden="true" />
          </span>
        )}
        <span
          className="absolute bottom-1.5 right-1.5 rounded px-1.5 py-0.5 text-[11px] font-semibold text-white"
          style={{ background: 'var(--overlay)' }}
        >
          {formatClipDuration(template.duration_seconds)}
        </span>
        {selected && (
          <span
            className="absolute left-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-black"
            aria-hidden="true"
          >
            <Check size={14} strokeWidth={3} />
          </span>
        )}
      </div>
      <p className="truncate px-1 pb-1 text-xs font-semibold text-white">{template.title}</p>
    </button>
  )
}
