import { useEffect, useRef, useState, type RefObject } from 'react'
import { Music2, X } from 'lucide-react'

import { getSongDetail } from '../api/songs.api'
import type { LibrarySong } from '../api/songs.api'
import { parseLyrics, type LyricsLine } from '../lib/lyrics-parser'

interface LyricsViewProps {
  song: LibrarySong
  audioRef: RefObject<HTMLAudioElement | null>
  onClose: () => void
}

export function LyricsView({ song, audioRef, onClose }: LyricsViewProps) {
  const [lines, setLines] = useState<LyricsLine[]>([])
  const [activeIdx, setActiveIdx] = useState(-1)
  const [loading, setLoading] = useState(true)
  const [isInstrumental, setIsInstrumental] = useState(false)
  const activeLineRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLines([])
    setActiveIdx(-1)
    setIsInstrumental(false)

    getSongDetail(song.id)
      .then((detail) => {
        if (cancelled) {
          return
        }
        const lyricsText = detail.lyrics || ''
        if (!lyricsText || detail.instrumental) {
          setIsInstrumental(true)
        } else {
          setLines(parseLyrics(lyricsText, detail.audio_duration ?? 180))
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIsInstrumental(true)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [song.id])

  useEffect(() => {
    if (lines.length === 0) {
      return
    }
    const id = window.setInterval(() => {
      if (!audioRef.current) {
        return
      }
      const t = audioRef.current.currentTime
      let next = -1
      for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i]
        if (line.type === 'lyric' && line.startTime >= 0) {
          if (line.startTime <= t) {
            next = i
          } else {
            break
          }
        }
      }
      setActiveIdx((prev) => (prev === next ? prev : next))
    }, 200)
    return () => window.clearInterval(id)
  }, [lines, audioRef])

  useEffect(() => {
    activeLineRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [activeIdx])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div
      className="fixed inset-x-0 top-0 bottom-[72px] z-40 flex flex-col lg:left-[264px]"
      style={{ background: 'linear-gradient(160deg, var(--bg-base) 0%, var(--bg-card) 100%)' }}
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Cerrar letra"
        className="absolute right-5 top-4 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20"
      >
        <X size={16} aria-hidden="true" />
      </button>

      <div className="shrink-0 px-6 pt-5 sm:px-16">
        <p className="text-[11px] font-semibold text-muted">Letra</p>
        <p className="max-w-[80%] truncate text-base font-semibold text-white">{song.title}</p>
      </div>

      <div className="relative mt-3 flex-1 overflow-hidden">
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-10 h-24"
          style={{ background: 'linear-gradient(to bottom, var(--bg-base) 0%, transparent 100%)' }}
        />

        <div className="h-full overflow-y-auto px-6 py-[32vh] sm:px-16 scrollbar-hidden">
          {loading && <div className="pt-12 text-center text-sm text-muted">Cargando letra...</div>}

          {!loading && isInstrumental && (
            <div className="flex flex-col items-center justify-center gap-3 pt-12 text-muted">
              <Music2 size={40} className="opacity-30" aria-hidden="true" />
              <p className="text-sm">Canción instrumental — sin letra</p>
            </div>
          )}

          {!loading &&
            !isInstrumental &&
            lines.map((line, i) => {
              const isActive = i === activeIdx
              const dist = Math.abs(i - activeIdx)
              if (line.type === 'section') {
                return (
                  <div key={i} className="my-6 text-[11px] font-bold tracking-[0.16em] text-primary">
                    {line.text.replace(/[[\]]/g, '').toUpperCase()}
                  </div>
                )
              }
              if (line.type === 'cue') {
                return (
                  <div key={i} className="mb-3 text-sm italic text-muted">
                    {line.text}
                  </div>
                )
              }
              const opacity = isActive ? 1 : dist === 1 ? 0.45 : dist === 2 ? 0.22 : 0.1
              const sizeClass = isActive
                ? 'text-3xl sm:text-4xl font-extrabold'
                : dist === 1
                  ? 'text-xl sm:text-2xl font-semibold'
                  : 'text-lg sm:text-xl font-semibold'
              return (
                <div
                  key={i}
                  ref={isActive ? activeLineRef : null}
                  className={`mb-5 leading-snug text-white transition-all duration-300 ${sizeClass}`}
                  style={{ opacity }}
                >
                  {line.text}
                </div>
              )
            })}
        </div>

        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-24"
          style={{ background: 'linear-gradient(to top, var(--bg-base) 0%, transparent 100%)' }}
        />
      </div>
    </div>
  )
}

export default LyricsView
