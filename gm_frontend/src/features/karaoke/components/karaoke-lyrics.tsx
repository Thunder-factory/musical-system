import { useEffect, useRef, useState } from 'react'
import type { LyricTimestamp } from '../../../types'

interface Props {
  timestamps: LyricTimestamp[]
  audioRef: React.RefObject<HTMLAudioElement | null>
  scrollRef?: React.RefObject<HTMLDivElement | null>
}

function splitLine(text: string): string[] {
  const MAX = 40
  if (text.length <= MAX) {
    return [text]
  }
  const commas: number[] = []
  for (let i = 0; i < text.length; i++) {
    if (text[i] === ',') {
      commas.push(i)
    }
  }
  const mid = text.length / 2
  if (commas.length > 0) {
    const best = commas.reduce((a, b) => (Math.abs(b - mid) < Math.abs(a - mid) ? b : a))
    return [text.slice(0, best + 1).trim(), text.slice(best + 1).trim()].filter(Boolean)
  }

  let splitAt = -1
  let bestDist = Infinity
  for (let i = 0; i < text.length; i++) {
    if (text[i] === ' ') {
      const d = Math.abs(i - mid)
      if (d < bestDist) {
        bestDist = d
        splitAt = i
      }
    }
  }
  if (splitAt === -1) {
    return [text]
  }
  return [text.slice(0, splitAt).trim(), text.slice(splitAt + 1).trim()]
}

export default function KaraokeLyrics({ timestamps, audioRef, scrollRef }: Props) {
  const [activeIdx, setActiveIdx] = useState(-1)
  const [autoScroll, setAutoScroll] = useState(true)
  const activeRef = useRef<HTMLDivElement>(null)
  const isProgrammatic = useRef(false)
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const programmaticTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    if (timestamps.length === 0) {
      return
    }
    const id = setInterval(() => {
      const t = audioRef.current?.currentTime ?? 0
      let found = -1
      for (let i = timestamps.length - 1; i >= 0; i--) {
        if (t >= timestamps[i].start) {
          found = i
          break
        }
      }
      setActiveIdx((prev) => (prev === found ? prev : found))
    }, 100)
    return () => clearInterval(id)
  }, [timestamps, audioRef])

  useEffect(() => {
    if (!autoScroll || activeIdx < 0) {
      return
    }
    const el = activeRef.current
    if (!el) {
      return
    }
    isProgrammatic.current = true
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    clearTimeout(programmaticTimer.current)
    programmaticTimer.current = setTimeout(() => {
      isProgrammatic.current = false
    }, 650)
  }, [activeIdx, autoScroll])

  useEffect(() => {
    const container = scrollRef?.current
    if (!container) {
      return
    }
    const onScroll = () => {
      if (isProgrammatic.current) {
        return
      }
      setAutoScroll(false)
      clearTimeout(resumeTimer.current)
      resumeTimer.current = setTimeout(() => setAutoScroll(true), 4000)
    }
    container.addEventListener('scroll', onScroll, { passive: true })
    return () => container.removeEventListener('scroll', onScroll)
  }, [scrollRef])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) {
      return
    }
    const recenter = () => {
      clearTimeout(resumeTimer.current)
      setAutoScroll(true)
    }
    audio.addEventListener('play', recenter)
    audio.addEventListener('pause', recenter)
    audio.addEventListener('seeked', recenter)
    return () => {
      audio.removeEventListener('play', recenter)
      audio.removeEventListener('pause', recenter)
      audio.removeEventListener('seeked', recenter)
    }
  }, [audioRef])

  useEffect(() => {
    return () => {
      clearTimeout(resumeTimer.current)
      clearTimeout(programmaticTimer.current)
    }
  }, [])

  return (
    <>
      {timestamps.map((ts, i) => {
        const isActive = i === activeIdx
        const dist = Math.abs(i - activeIdx)

        if (/^♪/.test(ts.text) && ts.text.endsWith('♪')) {
          return (
            <div
              key={i}
              className="my-2 mt-6 w-full text-center text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--color-success-muted)] transition-opacity duration-500"
              style={{ opacity: dist <= 1 ? 1 : 0.4 }}
            >
              {ts.text}
            </div>
          )
        }

        const opacity = isActive ? 1 : dist === 1 ? 0.5 : dist === 2 ? 0.28 : 0.14
        const blur = isActive ? 0 : dist === 1 ? 0.6 : dist === 2 ? 1.2 : 1.8
        const fontSize = isActive ? 38 : dist === 1 ? 24 : 19

        return (
          <div
            key={i}
            ref={isActive ? activeRef : null}
            className={`mb-6 w-full text-center leading-[1.22] text-white transition-all duration-500 ${
              isActive ? 'font-extrabold' : 'font-semibold'
            }`}
            style={{
              opacity,
              fontSize,
              filter: blur ? `blur(${blur}px)` : 'none',
              transform: isActive ? 'scale(1)' : 'scale(0.97)',
            }}
          >
            {splitLine(ts.text).map((line, j) => (
              <div key={j}>{line}</div>
            ))}
          </div>
        )
      })}
    </>
  )
}
