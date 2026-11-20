import { useCallback, useEffect, useRef, useState } from 'react'

import type { MixClip } from '../api/mix.api'
import styles from './clip-timeline.module.css'
import TimelineRuler from './timeline-ruler'

export interface TrackItem {
  clip: MixClip
  index: number
  durationMs: number
  startMs: number
  color: string
}

interface TimelineLanesProps {
  tracks: TrackItem[]
  totalMs: number
  canvasWidth: number
  pixelsPerSecond: number
  selectedClipId: string | null
  draggingClipId: string | null
  playheadMs: number | null
  playheadPct: number | null
  onPlayheadChange: (ms: number) => void
  onSelectClip: (id: string) => void
  onOpenContext: (id: string) => void
  getDragHandlers: (clipId: string, startMs: number) => Record<string, unknown>
}

const formatTime = (ms: number) => {
  const sec = Math.floor(ms / 1000)
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
}

export default function TimelineLanes({
  tracks,
  totalMs,
  canvasWidth,
  pixelsPerSecond,
  selectedClipId,
  draggingClipId,
  playheadMs,
  playheadPct,
  onPlayheadChange,
  onSelectClip,
  onOpenContext,
  getDragHandlers,
}: TimelineLanesProps) {
  const [draggingPlayhead, setDraggingPlayhead] = useState(false)
  const laneAreaRef = useRef<HTMLDivElement>(null)

  const setPlayheadFromClientX = useCallback(
    (clientX: number) => {
      const el = laneAreaRef.current
      if (!el) {
        return
      }
      const rect = el.getBoundingClientRect()
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
      onPlayheadChange(Math.round(ratio * totalMs))
    },
    [onPlayheadChange, totalMs]
  )

  useEffect(() => {
    if (!draggingPlayhead) {
      return
    }
    const onMove = (e: PointerEvent) => setPlayheadFromClientX(e.clientX)
    const onUp = () => setDraggingPlayhead(false)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [draggingPlayhead, setPlayheadFromClientX])

  return (
    <div className={styles.scrollArea}>
      <div className={styles.canvas} style={{ width: `${canvasWidth}px` }}>
        <div
          onPointerDown={(e) => setPlayheadFromClientX(e.clientX)}
          role="presentation"
        >
          <TimelineRuler totalMs={totalMs} pixelsPerSecond={pixelsPerSecond} />
        </div>

        <div
          ref={laneAreaRef}
          className={styles.laneArea}
          onPointerDown={(e) => setPlayheadFromClientX(e.clientX)}
          role="presentation"
        >
          {playheadPct !== null && (
            <div
              className={styles.playhead}
              style={{ left: `${playheadPct}%` }}
              aria-label={`Cabezal en ${playheadMs} milisegundos`}
              role="slider"
              aria-valuemin={0}
              aria-valuemax={totalMs}
              aria-valuenow={playheadMs ?? 0}
              tabIndex={0}
              onPointerDown={(e) => {
                e.stopPropagation()
                setDraggingPlayhead(true)
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowLeft') {
                  onPlayheadChange(Math.max(0, (playheadMs ?? 0) - 100))
                } else if (e.key === 'ArrowRight') {
                  onPlayheadChange(Math.min(totalMs, (playheadMs ?? 0) + 100))
                }
              }}
            />
          )}

          {tracks.map(({ clip, durationMs, startMs, color }) => {
            const isSelected = clip.id === selectedClipId
            const title =
              clip.custom_audio_name ?? clip.song_detail?.title ?? `Clip #${clip.position + 1}`
            return (
              <div className={styles.trackLane} key={clip.id}>
                <button
                  type="button"
                  className={`${styles.clipSegment} ${isSelected ? styles.clipSegmentSelected : ''} ${draggingClipId === clip.id ? styles.clipSegmentDragging : ''}`}
                  style={{
                    left: `${(startMs / totalMs) * 100}%`,
                    width: `${(durationMs / totalMs) * 100}%`,
                    background: color,
                    border: clip.is_external ? '2px dashed var(--color-info)' : undefined,
                  }}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelectClip(clip.id)
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault()
                    onOpenContext(clip.id)
                  }}
                  {...getDragHandlers(clip.id, startMs)}
                  aria-pressed={isSelected}
                  aria-label={`Seleccionar ${title}`}
                  title={`${title} · ${formatTime(durationMs)}`}
                >
                  <span>{formatTime(durationMs)}</span>
                </button>
              </div>
            )
          })}

          {[0, 1].map((idx) => (
            <div className={styles.trackLaneEmpty} key={idx}>
              {tracks.length === 0 && idx === 0 && (
                <span>Agrega clips desde la biblioteca para armar tu mix</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
