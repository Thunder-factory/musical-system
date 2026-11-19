import { useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'

import { containBox } from '../components/faceswap/face-target-geometry'
import type { FrameBox } from '../components/faceswap/face-target-geometry'

/**
 * Estado del <video> del selector de personaje: reproducción, tiempo, duración y el
 * rectángulo real del fotograma (se recalcula al redimensionar con ResizeObserver).
 */
export function useFaceTargetVideo() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [natural, setNatural] = useState({ w: 0, h: 0 })
  const [size, setSize] = useState({ w: 0, h: 0 })

  useEffect(() => {
    const video = videoRef.current
    if (!video) {
      return
    }
    const observer = new ResizeObserver(([entry]) => {
      setSize({ w: entry.contentRect.width, h: entry.contentRect.height })
    })
    observer.observe(video)
    return () => observer.disconnect()
  }, [])

  const handlers = {
    onLoadedMetadata: (e: SyntheticEvent<HTMLVideoElement>) => {
      const v = e.currentTarget
      setNatural({ w: v.videoWidth, h: v.videoHeight })
      setDuration(Number.isFinite(v.duration) ? v.duration : 0)
    },
    onTimeUpdate: (e: SyntheticEvent<HTMLVideoElement>) => setTime(e.currentTarget.currentTime),
    onPlay: () => setPlaying(true),
    onPause: () => setPlaying(false),
    onEnded: () => setPlaying(false),
  }

  function toggle() {
    const video = videoRef.current
    if (!video) {
      return
    }
    if (video.paused) {
      void video.play().catch(() => setPlaying(false))
    } else {
      video.pause()
    }
  }

  function seek(seconds: number) {
    const video = videoRef.current
    if (!video) {
      return
    }
    video.pause()
    video.currentTime = seconds
    setTime(seconds)
  }

  const box: FrameBox | null = containBox(size.w, size.h, natural.w, natural.h)
  const ready = natural.w > 0 && natural.h > 0
  /** Proporción del fotograma para dimensionar la caja (null hasta leer los metadatos). */
  const ratio = ready ? natural.w / natural.h : null

  return { videoRef, handlers, playing, time, duration, box, ready, ratio, toggle, seek }
}
