import { useEffect, useMemo, useRef, useState } from 'react'
import { Lightbulb, Mic, Pause, Play, Shuffle } from 'lucide-react'

import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import {
  generateMelody,
  INSPIRATION_STYLES,
  melodySeconds,
  midiToName,
  playMelody,
} from '../lib/melody-generator'

interface InspirationPanelProps {
  disabled: boolean
  onRecord: () => void
}

const SURPRISE = 'sorpresa'

function randomSeed() {
  return Math.floor(Math.random() * 1e9)
}

function randomStyleKey() {
  return INSPIRATION_STYLES[Math.floor(Math.random() * INSPIRATION_STYLES.length)].key
}

export default function InspirationPanel({ disabled, onRecord }: InspirationPanelProps) {
  const [open, setOpen] = useState(false)
  const [styleKey, setStyleKey] = useState(INSPIRATION_STYLES[0].key)
  const [seed, setSeed] = useState(randomSeed)
  const [playing, setPlaying] = useState(false)
  const [current, setCurrent] = useState(-1)
  const stopRef = useRef<(() => void) | null>(null)

  const style = INSPIRATION_STYLES.find((item) => item.key === styleKey) ?? INSPIRATION_STYLES[0]
  const melody = useMemo(() => generateMelody(style, seed), [style, seed])

  useEffect(() => () => stopRef.current?.(), [])

  function stop() {
    stopRef.current?.()
    stopRef.current = null
    setPlaying(false)
  }

  function togglePlay() {
    if (playing) {
      stop()
      return
    }
    setPlaying(true)
    stopRef.current = playMelody(melody, setCurrent, () => {
      stopRef.current = null
      setPlaying(false)
    })
  }

  function another(nextStyle?: string) {
    stop()
    if (nextStyle === SURPRISE) {
      setStyleKey(randomStyleKey())
    } else if (nextStyle) {
      setStyleKey(nextStyle)
    }
    setSeed(randomSeed())
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 self-start text-sm text-muted transition-colors hover:text-white"
      >
        <Lightbulb size={16} aria-hidden="true" />
        ¿No sabes qué tararear? Inspírate
      </button>
    )
  }

  const width = 600
  const height = 110
  const pitches = melody.notes.map((note) => note.midi)
  const low = Math.min(...pitches) - 1
  const high = Math.max(...pitches) + 1
  const x = (beat: number) => (beat / melody.beats) * width
  const y = (midi: number) => height - ((midi - low) / (high - low)) * height

  return (
    <section
      className="flex flex-col gap-3 rounded-xl border border-border-strong bg-card-hover p-4"
      aria-labelledby="inspiration-title"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 id="inspiration-title" className="inline-flex items-center gap-2 text-sm font-semibold text-white">
            <Lightbulb size={16} className="text-primary" aria-hidden="true" />
            Inspírate
          </h3>
          <p className="mt-1 text-xs text-muted">
            Escucha una melodía de ejemplo, apréndela y grábate tarareándola con «na-na».
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            stop()
            setOpen(false)
          }}
          className="shrink-0 text-xs text-muted hover:text-white"
        >
          Cerrar
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Estilo de la melodía de ejemplo">
        {INSPIRATION_STYLES.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => another(item.key)}
            aria-pressed={item.key === styleKey}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              item.key === styleKey
                ? 'border-primary bg-primary text-black'
                : 'border-border-strong bg-card text-white hover:border-primary'
            )}
          >
            {item.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => another(SURPRISE)}
          className="inline-flex items-center gap-1 rounded-full border border-border-strong bg-card px-3 py-1 text-xs text-white hover:border-primary"
        >
          <Shuffle size={12} aria-hidden="true" /> Sorpréndeme
        </button>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-24 w-full rounded-md bg-card"
        role="img"
        aria-label={`Melodía de ejemplo en estilo ${style.label}: ${melody.notes.length} notas`}
      >
        {[4, 8, 12].map((beat) => (
          <line
            key={beat}
            x1={x(beat)}
            x2={x(beat)}
            y1={0}
            y2={height}
            stroke="var(--border-strong)"
            strokeDasharray="3 4"
          />
        ))}
        {melody.notes.map((note, index) => (
          <rect
            key={`${note.start}-${index}`}
            x={x(note.start) + 1}
            y={y(note.midi) - 5}
            width={Math.max(4, x(note.duration) - 3)}
            height={10}
            rx={4}
            fill={index === current ? 'var(--color-primary-hover)' : 'var(--color-primary)'}
            opacity={current === -1 || index === current ? 1 : 0.45}
          />
        ))}
      </svg>

      <p className="text-xs text-muted">
        {style.label} · {melody.bpm} BPM · {Math.round(melodySeconds(melody))} s · empieza en{' '}
        {midiToName(melody.notes[0].midi)}. Tip: tararéala dos veces seguidas.
      </p>

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={togglePlay}
          leftIcon={
            playing ? (
              <Pause size={14} fill="currentColor" aria-hidden="true" />
            ) : (
              <Play size={14} fill="currentColor" aria-hidden="true" />
            )
          }
        >
          {playing ? 'Detener' : 'Escuchar'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => another()}
          leftIcon={<Shuffle size={14} aria-hidden="true" />}
        >
          Otra melodía
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled}
          onClick={() => {
            stop()
            onRecord()
          }}
          leftIcon={<Mic size={14} aria-hidden="true" />}
        >
          Grabarme imitándola
        </Button>
      </div>
    </section>
  )
}
