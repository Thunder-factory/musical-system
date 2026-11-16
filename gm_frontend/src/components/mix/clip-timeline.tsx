import { useCallback, useEffect, useRef, useState } from 'react'
import { ZoomIn, ZoomOut } from 'lucide-react'
import type { MixClip } from '../../api/modules/mix.api'
import useTimelineDrag from '../../hooks/useTimelineDrag'
import TrackHeader from './track-header'
import TimelineRuler from './timeline-ruler'
import ClipContextDialog from './clip-context-dialog'
import styles from './clip-timeline.module.css'

interface ClipTimelineProps {
  clips: MixClip[]
  selectedClipId: string | null
  onSelectClip: (id: string) => void
  onContextSelectClip: (id: string) => void
  onPreviewPosition: (clipId: string, timelineStartMs: number) => void
  onCommitPosition: (
    clipId: string,
    timelineStartMs: number,
    initialTimelineStartMs: number
  ) => void
  playheadMs: number | null
  onPlayheadChange: (playheadMs: number) => void
  playingClipId: string | null
  playbackState: 'idle' | 'playing' | 'paused'
  playbackMode: 'global' | 'individual' | null
  mutedClipIds: Record<string, boolean>
  soloClipIds: Record<string, boolean>
  onToggleClipPlayback: (clipId: string) => void
  onToggleMute: (clipId: string) => void
  onToggleSolo: (clipId: string) => void
  onSplitClip: (clipId: string) => Promise<void>
  onDeleteClip: (clipId: string) => Promise<void>
  onAddClip: () => void
}

const TRACK_COLORS = [
  'var(--color-primary)',
  'var(--color-primary-deep)',
  'var(--color-primary-hover)',
  'var(--color-success)',
  'var(--color-info)',
]

const BASE_PIXELS_PER_SECOND = 28
const MIN_ZOOM = 0.1
const MAX_ZOOM = 20
const MIN_TIMELINE_MS = 4 * 60 * 1000
const TIMELINE_PADDING_MS = 50 * 1000
const EMPTY_TRACK_SLOTS = 2

function formatTime(milliseconds: number) {
  const seconds = Math.floor(milliseconds / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export default function ClipTimeline({
  clips,
  selectedClipId,
  onSelectClip,
  onContextSelectClip,
  onPreviewPosition,
  onCommitPosition,
  playheadMs,
  onPlayheadChange,
  playingClipId,
  playbackState,
  playbackMode,
  mutedClipIds,
  soloClipIds,
  onToggleClipPlayback,
  onToggleMute,
  onToggleSolo,
  onSplitClip,
  onDeleteClip,
  onAddClip,
}: ClipTimelineProps) {
  const [zoom, setZoom] = useState(1)
  const [contextClipId, setContextClipId] = useState<string | null>(null)
  const [draggingPlayhead, setDraggingPlayhead] = useState(false)
  const laneAreaRef = useRef<HTMLDivElement>(null)
  const pixelsPerSecond = BASE_PIXELS_PER_SECOND * zoom
  const { draggingClipId, getDragHandlers } = useTimelineDrag({
    pixelsPerSecond,
    onStart: onSelectClip,
    onPreview: onPreviewPosition,
    onCommit: onCommitPosition,
  })

  const tracks = clips
    .slice()
    .sort((a, b) => a.position - b.position)
    .map((clip, index) => {
      const durationMs = Math.max(clip.duration_ms, 1)
      const startMs = Math.max(clip.timeline_start_ms ?? 0, 0)
      return {
        clip,
        index,
        durationMs,
        startMs,
        color: TRACK_COLORS[index % TRACK_COLORS.length],
      }
    })
  const contentEndMs = tracks.length
    ? Math.max(...tracks.map(({ startMs, durationMs }) => startMs + durationMs))
    : 0
  const totalMs = Math.max(MIN_TIMELINE_MS, contentEndMs + TIMELINE_PADDING_MS)
  const canvasWidth = Math.max(320, (totalMs / 1000) * pixelsPerSecond)
  const playheadPct = playheadMs === null ? null : Math.min((playheadMs / totalMs) * 100, 100)

  const setPlayheadFromClientX = useCallback(
    (clientX: number) => {
      const element = laneAreaRef.current
      if (!element) {
        return
      }
      const rect = element.getBoundingClientRect()
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
      onPlayheadChange(Math.round(ratio * totalMs))
    },
    [onPlayheadChange, totalMs]
  )

  function setPlayheadFromEvent(event: React.MouseEvent<HTMLElement>) {
    setPlayheadFromClientX(event.clientX)
  }

  useEffect(() => {
    if (!draggingPlayhead) {
      return
    }

    function handlePointerMove(event: PointerEvent) {
      setPlayheadFromClientX(event.clientX)
    }

    function handlePointerUp() {
      setDraggingPlayhead(false)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
    }
  }, [draggingPlayhead, setPlayheadFromClientX])

  return (
    <section className={styles.timeline} aria-label="Timeline del mix">
      <div className={styles.heading}>
        <div className={styles.headingTitle}>
          <span>Timeline · {tracks.length} clips</span>
          <button type="button" className={styles.addButton} onClick={onAddClip}>
            + Agregar
          </button>
        </div>
        <div className={styles.headingTools}>
          <span>{Math.round(pixelsPerSecond)} px/s</span>
          <button
            type="button"
            className={styles.zoomButton}
            onClick={() => setZoom((value) => Math.max(MIN_ZOOM, value / 1.5))}
            disabled={zoom <= MIN_ZOOM}
            aria-label="Alejar timeline"
            title="Alejar"
          >
            <ZoomOut size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={styles.zoomButton}
            onClick={() => setZoom(1)}
            aria-label="Restablecer zoom"
            title="Restablecer zoom"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            type="button"
            className={styles.zoomButton}
            onClick={() => setZoom((value) => Math.min(MAX_ZOOM, value * 1.5))}
            disabled={zoom >= MAX_ZOOM}
            aria-label="Acercar timeline"
            title="Acercar"
          >
            <ZoomIn size={13} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className={styles.editorGrid}>
        <div className={styles.trackHeaders} aria-label="Controles de pistas">
          <div className={styles.headerSpacer}>Pistas</div>
          {tracks.map(({ clip, index, color, startMs, durationMs }) => (
            <TrackHeader
              key={clip.id}
              clip={clip}
              index={index}
              color={color}
              isSelected={clip.id === selectedClipId}
              isPlaying={
                playbackState === 'playing' &&
                (playingClipId === clip.id ||
                  (playbackMode === 'global' &&
                    playheadMs !== null &&
                    playheadMs >= startMs &&
                    playheadMs < startMs + durationMs))
              }
              muted={Boolean(mutedClipIds[clip.id])}
              solo={Boolean(soloClipIds[clip.id])}
              onSelect={() => onSelectClip(clip.id)}
              onTogglePlay={() => {
                onSelectClip(clip.id)
                onToggleClipPlayback(clip.id)
              }}
              onToggleMute={() => onToggleMute(clip.id)}
              onToggleSolo={() => onToggleSolo(clip.id)}
            />
          ))}
          {Array.from({ length: EMPTY_TRACK_SLOTS }, (_, index) => (
            <div className={styles.trackHeaderEmpty} key={`empty-header-${index}`}>
              <span>Pista disponible</span>
              <small>Agrega un clip</small>
            </div>
          ))}
        </div>

        <div className={styles.scrollArea}>
          <div className={styles.canvas} style={{ width: `${canvasWidth}px` }}>
            <div onClick={setPlayheadFromEvent} role="presentation">
              <TimelineRuler totalMs={totalMs} pixelsPerSecond={pixelsPerSecond} />
            </div>

            <div
              ref={laneAreaRef}
              className={styles.laneArea}
              onClick={setPlayheadFromEvent}
              role="presentation"
            >
              {playheadPct !== null && (
                <div
                  className={styles.playhead}
                  style={{ left: `${playheadPct}%` }}
                  aria-label={`Playhead en ${playheadMs} milisegundos`}
                  role="slider"
                  aria-valuemin={0}
                  aria-valuemax={totalMs}
                  aria-valuenow={playheadMs ?? 0}
                  tabIndex={0}
                  onClick={(event) => event.stopPropagation()}
                  onPointerDown={(event) => {
                    event.stopPropagation()
                    setDraggingPlayhead(true)
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'ArrowLeft') {
                      onPlayheadChange(Math.max(0, (playheadMs ?? 0) - 100))
                    }
                    if (event.key === 'ArrowRight') {
                      onPlayheadChange(Math.min(totalMs, (playheadMs ?? 0) + 100))
                    }
                  }}
                />
              )}
              {tracks.map(({ clip, durationMs, startMs, color }) => {
                const isSelected = clip.id === selectedClipId
                const title =
                  clip.custom_audio_name ?? clip.song_detail?.title ?? `Clip #${clip.position + 1}`
                const startPct = (startMs / totalMs) * 100
                const widthPct = (durationMs / totalMs) * 100

                return (
                  <div
                    className={styles.trackLane}
                    key={clip.id}
                    onClick={setPlayheadFromEvent}
                    role="presentation"
                  >
                    <button
                      type="button"
                      className={`${styles.clipSegment} ${isSelected ? styles.clipSegmentSelected : ''} ${draggingClipId === clip.id ? styles.clipSegmentDragging : ''}`}
                      style={{
                        left: `${startPct}%`,
                        width: `${widthPct}%`,
                        background: color,
                        border: clip.is_external
                          ? '2px dashed var(--color-info)'
                          : undefined,
                      }}
                      onClick={(event) => {
                        event.stopPropagation()
                        onSelectClip(clip.id)
                      }}
                      onContextMenu={(event) => {
                        event.preventDefault()
                        onContextSelectClip(clip.id)
                        setContextClipId(clip.id)
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
              {Array.from({ length: EMPTY_TRACK_SLOTS }, (_, index) => (
                <div className={styles.trackLaneEmpty} key={`empty-lane-${index}`}>
                  {clips.length === 0 && index === 0 && (
                    <span>Agrega clips desde la biblioteca para armar tu mix</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      {contextClipId &&
        (() => {
          const contextClip = clips.find((clip) => clip.id === contextClipId)
          if (!contextClip) {
            return null
          }
          return (
            <ClipContextDialog
              clip={contextClip}
              playheadMs={playheadMs}
              onSplit={() => onSplitClip(contextClip.id)}
              onDelete={() => onDeleteClip(contextClip.id)}
              onClose={() => setContextClipId(null)}
            />
          )
        })()}
    </section>
  )
}
