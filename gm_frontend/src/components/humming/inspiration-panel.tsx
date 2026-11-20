import { useEffect, useMemo, useRef, useState } from 'react'
import { Lightbulb, Mic, Pause, Play, Shuffle } from 'lucide-react'

import {
  generateMelody,
  INSPIRATION_STYLES,
  melodySeconds,
  midiToName,
  playMelody,
} from '../../lib/melody-generator'

interface Props {
  disabled: boolean
  onRecord: () => void
}

const SURPRISE = 'sorpresa'

// Fuera del componente: el azar solo se usa en respuesta a un clic.
function randomSeed() {
  return Math.floor(Math.random() * 1e9)
}

function randomStyleKey() {
  return INSPIRATION_STYLES[Math.floor(Math.random() * INSPIRATION_STYLES.length)].key
}

/**
 * "¿No sabes qué tararear?": genera una melodía corta en el estilo elegido para
 * escucharla e imitarla. No usa la red ni créditos.
 */
export default function InspirationPanel({ disabled, onRecord }: Props) {
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

  function record() {
    stop()
    onRecord()
  }

  // Dibujo tipo "piano roll": tiempo en X, altura en Y.
  const width = 600
  const height = 120
  const pitches = melody.notes.map((note) => note.midi)
  const low = Math.min(...pitches) - 1
  const high = Math.max(...pitches) + 1
  const x = (beat: number) => (beat / melody.beats) * width
  const y = (midi: number) => height - ((midi - low) / (high - low)) * height

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 text-sm text-muted hover:text-white self-start"
      >
        <Lightbulb size={16} aria-hidden="true" />
        ¿No sabes qué tararear? Inspírate
      </button>
    )
  }

  const chip = (selected: boolean) => ({
    background: selected ? 'var(--color-primary)' : 'var(--bg-card-hover)',
    color: selected ? 'var(--color-on-primary)' : 'var(--text-base)',
    border: `1px solid ${selected ? 'var(--color-primary)' : 'var(--border-strong)'}`,
  })

  return (
    <section
      className="rounded-lg p-4 flex flex-col gap-3"
      style={{ background: 'var(--bg-card-hover)', border: '1px solid var(--border-strong)' }}
      aria-labelledby="inspiration-title"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3
            id="inspiration-title"
            className="text-white text-sm font-semibold inline-flex items-center gap-2"
          >
            <Lightbulb size={16} style={{ color: 'var(--color-primary)' }} aria-hidden="true" />
            Inspírate
          </h3>
          <p className="text-xs text-muted mt-1">
            Escucha una melodía de ejemplo, apréndela y grábate tarareándola con «na-na». Si te sale
            distinta, mejor: será tuya.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            stop()
            setOpen(false)
          }}
          className="text-xs text-muted hover:text-white shrink-0"
        >
          Cerrar
        </button>
      </div>

      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Estilo de la melodía de ejemplo"
      >
        {INSPIRATION_STYLES.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => another(item.key)}
            aria-pressed={item.key === styleKey}
            className="rounded-pill px-3 py-1 text-xs"
            style={chip(item.key === styleKey)}
          >
            {item.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => another(SURPRISE)}
          className="rounded-pill px-3 py-1 text-xs inline-flex items-center gap-1"
          style={chip(false)}
        >
          <Shuffle size={12} aria-hidden="true" /> Sorpréndeme
        </button>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-28 rounded-md"
        style={{ background: 'var(--bg-card)' }}
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
        {midiToName(melody.notes[0].midi)}. Tip: tararéala dos veces seguidas para llegar a 15-20 s.
      </p>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={togglePlay}
          className="rounded-pill px-4 py-2 text-sm font-medium inline-flex items-center gap-2"
          style={{ background: 'var(--color-primary)', color: 'var(--color-on-primary)' }}
        >
          {playing ? (
            <Pause size={14} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={14} fill="currentColor" aria-hidden="true" />
          )}
          {playing ? 'Detener' : 'Escuchar'}
        </button>
        <button
          type="button"
          onClick={() => another()}
          className="rounded-pill px-4 py-2 text-sm text-white inline-flex items-center gap-2"
          style={{ border: '1px solid var(--border-strong)' }}
        >
          <Shuffle size={14} aria-hidden="true" /> Otra melodía
        </button>
        <button
          type="button"
          onClick={record}
          disabled={disabled}
          className="rounded-pill px-4 py-2 text-sm text-white inline-flex items-center gap-2 disabled:opacity-50"
          style={{ border: '1px solid var(--border-strong)' }}
        >
          <Mic size={14} aria-hidden="true" /> Grabarme imitándola
        </button>
      </div>
    </section>
  )
}
