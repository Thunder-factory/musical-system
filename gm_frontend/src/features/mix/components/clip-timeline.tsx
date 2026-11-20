import { useState } from 'react'
import { ZoomIn, ZoomOut } from 'lucide-react'

import type { MixClip } from '../api/mix.api'
import useTimelineDrag from '../hooks/useTimelineDrag'
import ClipContextDialog from './clip-context-dialog'
import styles from './clip-timeline.module.css'
import TimelineLanes from './timeline-lanes'
import TrackHeader from './track-header'

interface ClipTimelineProps {
  clips: MixClip[]
  selectedClipId: string | null
  onSelectClip: (id: string) => void
  onContextSelectClip: (id: string) => void
  onPreviewPosition: (clipId: string, timelineStartMs: number) => void
  onCommitPosition: (clipId: string, timelineStartMs: number, initialTimelineStartMs: number) => void
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
const BASE_PPS = 28
const MIN_ZOOM = 0.1
const MAX_ZOOM = 20
const MIN_MS = 4 * 60 * 1000
const PADDING_MS = 50 * 1000

export default function ClipTimeline(props: ClipTimelineProps) {
  const [zoom, setZoom] = useState(1)
  const [contextClipId, setContextClipId] = useState<string | null>(null)
  const pixelsPerSecond = BASE_PPS * zoom
  const { draggingClipId, getDragHandlers } = useTimelineDrag({
    pixelsPerSecond,
    onStart: props.onSelectClip,
    onPreview: props.onPreviewPosition,
    onCommit: props.onCommitPosition,
  })

  const tracks = props.clips
    .slice()
    .sort((a, b) => a.position - b.position)
    .map((clip, index) => ({
      clip,
      index,
      durationMs: Math.max(clip.duration_ms, 1),
      startMs: Math.max(clip.timeline_start_ms ?? 0, 0),
      color: TRACK_COLORS[index % TRACK_COLORS.length],
    }))
  const contentEndMs = tracks.length
    ? Math.max(...tracks.map((t) => t.startMs + t.durationMs))
    : 0
  const totalMs = Math.max(MIN_MS, contentEndMs + PADDING_MS)
  const canvasWidth = Math.max(320, (totalMs / 1000) * pixelsPerSecond)
  const playheadPct =
    props.playheadMs === null ? null : Math.min((props.playheadMs / totalMs) * 100, 100)
  const contextClip = contextClipId ? props.clips.find((c) => c.id === contextClipId) : null

  return (
    <section className={styles.timeline} aria-label="Línea de tiempo del mix">
      <div className={styles.heading}>
        <div className={styles.headingTitle}>
          <span>Línea de tiempo · {tracks.length} clips</span>
          <button type="button" className={styles.addButton} onClick={props.onAddClip}>
            + Agregar
          </button>
        </div>
        <div className={styles.headingTools}>
          <span>{Math.round(pixelsPerSecond)} px/s</span>
          <button
            type="button"
            className={styles.zoomButton}
            onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z / 1.5))}
            disabled={zoom <= MIN_ZOOM}
            aria-label="Alejar línea de tiempo"
          >
            <ZoomOut size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={styles.zoomButton}
            onClick={() => setZoom(1)}
            aria-label="Restablecer zoom"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            type="button"
            className={styles.zoomButton}
            onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z * 1.5))}
            disabled={zoom >= MAX_ZOOM}
            aria-label="Acercar línea de tiempo"
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
              isSelected={clip.id === props.selectedClipId}
              isPlaying={
                props.playbackState === 'playing' &&
                (props.playingClipId === clip.id ||
                  (props.playbackMode === 'global' &&
                    props.playheadMs !== null &&
                    props.playheadMs >= startMs &&
                    props.playheadMs < startMs + durationMs))
              }
              muted={Boolean(props.mutedClipIds[clip.id])}
              solo={Boolean(props.soloClipIds[clip.id])}
              onSelect={() => props.onSelectClip(clip.id)}
              onTogglePlay={() => {
                props.onSelectClip(clip.id)
                props.onToggleClipPlayback(clip.id)
              }}
              onToggleMute={() => props.onToggleMute(clip.id)}
              onToggleSolo={() => props.onToggleSolo(clip.id)}
            />
          ))}
          {[0, 1].map((idx) => (
            <div className={styles.trackHeaderEmpty} key={idx}>
              <span>Pista disponible</span>
              <small>Agrega un clip</small>
            </div>
          ))}
        </div>

        <TimelineLanes
          tracks={tracks}
          totalMs={totalMs}
          canvasWidth={canvasWidth}
          pixelsPerSecond={pixelsPerSecond}
          selectedClipId={props.selectedClipId}
          draggingClipId={draggingClipId}
          playheadMs={props.playheadMs}
          playheadPct={playheadPct}
          onPlayheadChange={props.onPlayheadChange}
          onSelectClip={props.onSelectClip}
          onOpenContext={(clipId) => {
            props.onContextSelectClip(clipId)
            setContextClipId(clipId)
          }}
          getDragHandlers={getDragHandlers}
        />
      </div>

      {contextClip && (
        <ClipContextDialog
          open
          clip={contextClip}
          playheadMs={props.playheadMs}
          onSplit={() => props.onSplitClip(contextClip.id)}
          onDelete={() => props.onDeleteClip(contextClip.id)}
          onClose={() => setContextClipId(null)}
        />
      )}
    </section>
  )
}
