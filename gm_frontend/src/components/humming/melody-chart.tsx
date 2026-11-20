import { useMemo, useRef, useState } from 'react'
import { ChartLine } from 'lucide-react'

import type { HummingChart } from '../../api/modules/humming.api'
import { midiToName } from '../../lib/melody-generator'

/**
 * "Tu tarareo vs. la canción": la altura real de tu voz (línea), las notas que
 * detectamos (barras finas) y la melodía que sigue la canción (barras anchas),
 * en el tiempo del tarareo. Eje Y en notas (con Hz al pasar el mouse).
 */

const SONG_COLOR = '#3b82f6' // validado contra --bg-card junto al naranja de la marca
const NOTES_COLOR = 'var(--color-primary)'
const VOICE_COLOR = 'var(--text-base)'

const W = 640
const H = 240
const PAD = { left: 44, right: 8, top: 8, bottom: 22 }

type SeriesKey = 'voz' | 'notas' | 'cancion'

const SERIES: { key: SeriesKey; label: string }[] = [
  { key: 'voz', label: 'Tu voz' },
  { key: 'notas', label: 'Notas detectadas' },
  { key: 'cancion', label: 'Melodía de la canción' },
]

function hz(midi: number) {
  return Math.round(440 * 2 ** ((midi - 69) / 12))
}

function noteName(midi: number) {
  return midiToName(Math.round(midi))
}

function noteAt(notes: [number, number, number][], t: number) {
  return notes.find(([, start, dur]) => t >= start && t < start + dur)
}

export default function MelodyChart({ chart }: { chart: HummingChart }) {
  const [hidden, setHidden] = useState<Set<SeriesKey>>(new Set())
  const [hoverT, setHoverT] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const geometry = useMemo(() => {
    // El rango sale de las notas: la curva de la voz trae saltos de octava
    // sueltos (errores típicos de YIN) que aplastarían el gráfico.
    const notePitches = [...chart.notas.map((n) => n[0]), ...chart.cancion.map((n) => n[0])]
    const voiced = chart.contorno.filter((v): v is number => v !== null)
    const pitches = notePitches.length > 0 ? notePitches : voiced
    const low = Math.floor(Math.min(...pitches)) - 2
    const high = Math.ceil(Math.max(...pitches)) + 2
    const duration = Math.max(
      chart.contorno.length * chart.pasoSegundos,
      ...chart.notas.map(([, s, d]) => s + d),
      ...chart.cancion.map(([, s, d]) => s + d)
    )
    const x = (t: number) => PAD.left + (t / duration) * (W - PAD.left - PAD.right)
    const y = (midi: number) =>
      PAD.top + ((high - midi) / (high - low)) * (H - PAD.top - PAD.bottom)
    const row = (H - PAD.top - PAD.bottom) / (high - low)

    // Línea de la voz, cortada donde no hay voz.
    let path = ''
    let drawing = false
    let previous: number | null = null
    chart.contorno.forEach((value, i) => {
      // Se corta donde no hay voz, fuera del rango o en un salto brusco (> 3 semitonos en 50 ms).
      const jump = previous !== null && value !== null && Math.abs(value - previous) > 3
      previous = value
      if (value === null || value < low || value > high || jump) {
        drawing = value !== null && value >= low && value <= high
        if (drawing && value !== null) {
          path += `M${x(i * chart.pasoSegundos).toFixed(1)} ${y(value).toFixed(1)} `
        }
        return
      }
      const px = x(i * chart.pasoSegundos).toFixed(1)
      const py = y(value).toFixed(1)
      path += `${drawing ? 'L' : 'M'}${px} ${py} `
      drawing = true
    })

    // Qué tanto tu voz cae dentro de la nota de la canción (± medio tono).
    let inside = 0
    let hits = 0
    chart.contorno.forEach((value, i) => {
      const note = value === null ? undefined : noteAt(chart.cancion, i * chart.pasoSegundos)
      if (value === null || !note) {
        return
      }
      inside += 1
      if (Math.abs(value - note[0]) <= 0.5) {
        hits += 1
      }
    })

    const labelEvery = Math.max(1, Math.ceil((high - low) / 8))
    const secondsEvery = duration > 20 ? 5 : 2
    return {
      low,
      high,
      duration,
      x,
      y,
      row,
      path,
      labelEvery,
      secondsEvery,
      inTune: inside > 0 ? Math.round((hits / inside) * 100) : null,
    }
  }, [chart])

  if (chart.contorno.length === 0 && chart.cancion.length === 0) {
    return null
  }

  const { low, high, duration, x, y, row, path, labelEvery, secondsEvery, inTune } = geometry
  const show = (key: SeriesKey) => !hidden.has(key)

  function toggle(key: SeriesKey) {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  function handleMove(event: React.PointerEvent<SVGSVGElement>) {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) {
      return
    }
    const px = ((event.clientX - rect.left) / rect.width) * W
    const t = ((px - PAD.left) / (W - PAD.left - PAD.right)) * duration
    setHoverT(t >= 0 && t <= duration ? t : null)
  }

  const hover =
    hoverT === null
      ? null
      : {
          voice: chart.contorno[Math.round(hoverT / chart.pasoSegundos)] ?? null,
          song: noteAt(chart.cancion, hoverT),
          detected: noteAt(chart.notas, hoverT),
        }

  const rows = []
  for (let midi = low + 1; midi < high; midi += 1) {
    rows.push(midi)
  }
  const ticks = []
  for (let t = 0; t <= duration; t += secondsEvery) {
    ticks.push(t)
  }

  return (
    <section
      className="rounded-lg p-4 flex flex-col gap-3"
      style={{ background: 'var(--bg-card-hover)' }}
      aria-labelledby="melody-chart-title"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3
          id="melody-chart-title"
          className="text-white text-sm font-semibold inline-flex items-center gap-2"
        >
          <ChartLine size={16} style={{ color: 'var(--color-primary)' }} aria-hidden="true" />
          Tu tarareo vs. la canción
        </h3>
        {inTune !== null && (
          <p className="text-xs" style={{ color: 'var(--text-base-soft)' }}>
            Tu voz estuvo a menos de medio tono de la melodía el{' '}
            <span className="text-white font-semibold">{inTune} %</span> del tiempo
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Mostrar u ocultar series">
        {SERIES.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => toggle(item.key)}
            aria-pressed={show(item.key)}
            className="inline-flex items-center gap-2 rounded-pill px-3 py-1 text-xs"
            style={{
              border: '1px solid var(--border-strong)',
              color: show(item.key) ? 'var(--text-base)' : 'var(--text-base-muted)',
            }}
          >
            {item.key === 'voz' ? (
              <span className="w-4 h-0.5 rounded" style={{ background: VOICE_COLOR }} />
            ) : (
              <span
                className="w-4 rounded-sm"
                style={{
                  height: item.key === 'cancion' ? 8 : 4,
                  background: item.key === 'cancion' ? SONG_COLOR : NOTES_COLOR,
                  opacity: show(item.key) ? 1 : 0.4,
                }}
              />
            )}
            {item.label}
          </button>
        ))}
      </div>

      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto rounded-md touch-none"
          style={{ background: 'var(--bg-card)' }}
          role="img"
          aria-label={`Gráfico de alturas: tu voz y la melodía de la canción durante ${Math.round(duration)} segundos`}
          onPointerMove={handleMove}
          onPointerDown={handleMove}
          onPointerLeave={() => setHoverT(null)}
        >
          {rows.map((midi) => (
            <g key={midi}>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={y(midi)}
                y2={y(midi)}
                stroke="var(--border-strong)"
                strokeOpacity={midi % 12 === 0 ? 0.9 : 0.35}
                strokeWidth={1}
              />
              {(midi - low - 1) % labelEvery === 0 && (
                <text
                  x={PAD.left - 6}
                  y={y(midi) + 3}
                  textAnchor="end"
                  fontSize={10}
                  fill="var(--text-subdued)"
                >
                  {noteName(midi)}
                </text>
              )}
            </g>
          ))}
          {ticks.map((t) => (
            <text
              key={t}
              x={x(t)}
              y={H - 6}
              textAnchor="middle"
              fontSize={10}
              fill="var(--text-subdued)"
            >
              {t} s
            </text>
          ))}

          {show('cancion') &&
            chart.cancion.map(([midi, start, dur], i) => (
              <rect
                key={`c${i}`}
                x={x(start) + 1}
                y={y(midi) - row * 0.4}
                width={Math.max(2, x(start + dur) - x(start) - 2)}
                height={row * 0.8}
                rx={3}
                fill={SONG_COLOR}
                fillOpacity={0.45}
              />
            ))}
          {show('notas') &&
            chart.notas.map(([midi, start, dur], i) => (
              <rect
                key={`n${i}`}
                x={x(start) + 1}
                y={y(midi) - Math.min(3, row * 0.2)}
                width={Math.max(2, x(start + dur) - x(start) - 2)}
                height={Math.min(6, row * 0.4)}
                rx={2}
                fill={NOTES_COLOR}
              />
            ))}
          {show('voz') && path && (
            <path
              d={path}
              fill="none"
              stroke={VOICE_COLOR}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}

          {hoverT !== null && (
            <line
              x1={x(hoverT)}
              x2={x(hoverT)}
              y1={PAD.top}
              y2={H - PAD.bottom}
              stroke="var(--text-base-soft)"
              strokeWidth={1}
            />
          )}
        </svg>

        {hover && hoverT !== null && (
          <div
            className="absolute top-1 pointer-events-none rounded-md px-2 py-1 text-xs flex flex-col gap-0.5"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-strong)',
              color: 'var(--text-base)',
              left: `${(x(hoverT) / W) * 100}%`,
              transform: x(hoverT) > W * 0.6 ? 'translateX(calc(-100% - 8px))' : 'translateX(8px)',
              whiteSpace: 'nowrap',
            }}
          >
            <span style={{ color: 'var(--text-subdued)' }}>{hoverT.toFixed(1)} s</span>
            <span>
              Tu voz:{' '}
              {hover.voice === null ? '—' : `${noteName(hover.voice)} · ${hz(hover.voice)} Hz`}
            </span>
            <span>
              Detectada:{' '}
              {hover.detected
                ? `${noteName(hover.detected[0])} · ${hz(hover.detected[0])} Hz`
                : '—'}
            </span>
            <span>
              Canción: {hover.song ? `${noteName(hover.song[0])} · ${hz(hover.song[0])} Hz` : '—'}
            </span>
          </div>
        )}
      </div>

      <p className="text-xs text-muted">
        La línea es la altura real de tu voz; las barras naranjas, las notas que detectamos; y las
        azules, la melodía ajustada al pulso que usan tus canciones.
      </p>

      <details className="text-xs text-muted">
        <summary className="cursor-pointer hover:text-white">Ver la melodía como tabla</summary>
        <table className="mt-2 w-full text-left">
          <thead>
            <tr>
              <th className="font-medium py-1">Nota</th>
              <th className="font-medium py-1">Frecuencia</th>
              <th className="font-medium py-1">Inicio</th>
              <th className="font-medium py-1">Duración</th>
            </tr>
          </thead>
          <tbody>
            {chart.cancion.map(([midi, start, dur], i) => (
              <tr key={i} style={{ color: 'var(--text-base-soft)' }}>
                <td className="py-0.5">{noteName(midi)}</td>
                <td className="py-0.5">{hz(midi)} Hz</td>
                <td className="py-0.5">{start.toFixed(2)} s</td>
                <td className="py-0.5">{dur.toFixed(2)} s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}
