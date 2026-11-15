import { useCallback, useRef, useState } from 'react'

interface DragState {
  clipId: string
  initialPointerX: number
  initialTimelineStartMs: number
  currentTimelineStartMs: number
  pointerId: number
}

interface UseTimelineDragOptions {
  pixelsPerSecond: number
  onStart?: (clipId: string) => void
  onPreview: (clipId: string, timelineStartMs: number) => void
  onCommit: (clipId: string, timelineStartMs: number, initialTimelineStartMs: number) => void
}

export default function useTimelineDrag({
  pixelsPerSecond,
  onStart,
  onPreview,
  onCommit,
}: UseTimelineDragOptions) {
  const dragRef = useRef<DragState | null>(null)
  const [draggingClipId, setDraggingClipId] = useState<string | null>(null)

  const handlePointerDown = useCallback(
    (event: React.PointerEvent, clipId: string, timelineStartMs: number) => {
      if (event.button !== 0) {
        return
      }

      event.stopPropagation()
      event.currentTarget.setPointerCapture(event.pointerId)
      dragRef.current = {
        clipId,
        initialPointerX: event.clientX,
        initialTimelineStartMs: timelineStartMs,
        currentTimelineStartMs: timelineStartMs,
        pointerId: event.pointerId,
      }
      setDraggingClipId(clipId)
      onStart?.(clipId)
    },
    [onStart]
  )

  const handlePointerMove = useCallback(
    (event: React.PointerEvent) => {
      const drag = dragRef.current
      if (!drag || drag.pointerId !== event.pointerId) {
        return
      }

      const deltaMs = Math.round(((event.clientX - drag.initialPointerX) / pixelsPerSecond) * 1000)
      const timelineStartMs = Math.max(0, drag.initialTimelineStartMs + deltaMs)
      drag.currentTimelineStartMs = timelineStartMs
      onPreview(drag.clipId, timelineStartMs)
    },
    [onPreview, pixelsPerSecond]
  )

  const finishDrag = useCallback(
    (event: React.PointerEvent) => {
      const drag = dragRef.current
      if (!drag || drag.pointerId !== event.pointerId) {
        return
      }

      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId)
      }
      dragRef.current = null
      setDraggingClipId(null)

      if (drag.currentTimelineStartMs !== drag.initialTimelineStartMs) {
        onCommit(drag.clipId, drag.currentTimelineStartMs, drag.initialTimelineStartMs)
      }
    },
    [onCommit]
  )

  const getDragHandlers = useCallback(
    (clipId: string, timelineStartMs: number) => ({
      onPointerDown: (event: React.PointerEvent) =>
        handlePointerDown(event, clipId, timelineStartMs),
      onPointerMove: handlePointerMove,
      onPointerUp: finishDrag,
      onPointerCancel: finishDrag,
    }),
    [finishDrag, handlePointerDown, handlePointerMove]
  )

  return { draggingClipId, getDragHandlers }
}
