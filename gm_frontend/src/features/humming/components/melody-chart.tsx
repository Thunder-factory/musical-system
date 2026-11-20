import { useMemo, useRef, useState } from 'react'
import { ChartLine } from 'lucide-react'

import type { HummingChart } from '../api/humming.api'
import {
  CHART_H,
  CHART_PAD,
  CHART_W,
  computeChartGeometry,
  noteAt,
  noteName,
} from '../lib/melody-chart-geometry'
import {
  CHART_NOTES_COLOR,
  CHART_SONG_COLOR,
  CHART_VOICE_COLOR,
  MelodyChartLegend,
  MelodyChartTooltip,
  type ChartSeriesKey,
} from './melody-chart-legend'

export default function MelodyChart({ chart }: { chart: HummingChart }) {
  const [hidden, setHidden] = useState<Set<ChartSeriesKey>>(new Set())
  const [hoverT, setHoverT] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const geometry = useMemo(() => computeChartGeometry(chart), [chart])

  if (chart.contorno.length === 0 && chart.cancion.length === 0) {
    return null
  }

  const { low, high, duration, x, y, row, path, labelEvery, secondsEvery, inTune } = geometry
  const show = (key: ChartSeriesKey) => !hidden.has(key)

  function toggle(key: ChartSeriesKey) {
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
    const px = ((event.clientX - rect.left) / rect.width) * CHART_W
    const t = ((px - CHART_PAD.left) / (CHART_W - CHART_PAD.left - CHART_PAD.right)) * duration
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

  const rows: number[] = []
  for (let midi = low + 1; midi < high; midi += 1) {
    rows.push(midi)
  }
  const ticks: number[] = []
  for (let t = 0; t <= duration; t += secondsEvery) {
    ticks.push(t)
  }

  return (
    <section
      className="flex flex-col gap-3 rounded-xl bg-card-hover p-4"
      aria-labelledby="melody-chart-title"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3
          id="melody-chart-title"
          className="inline-flex items-center gap-2 text-sm font-semibold text-white"
        >
          <ChartLine size={16} className="text-primary" aria-hidden="true" />
          Tu tarareo vs. la canción
        </h3>
        {inTune !== null && (
          <p className="text-xs text-white/75">
            Tu voz estuvo a menos de medio tono de la melodía el{' '}
            <span className="font-semibold text-white">{inTune} %</span> del tiempo
          </p>
        )}
      </div>

      <MelodyChartLegend show={show} onToggle={toggle} />

      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${CHART_W} ${CHART_H}`}
          className="h-auto w-full touch-none rounded-md bg-card"
          role="img"
          aria-label={`Gráfico de alturas: tu voz y la melodía de la canción durante ${Math.round(duration)} segundos`}
          onPointerMove={handleMove}
          onPointerDown={handleMove}
          onPointerLeave={() => setHoverT(null)}
        >
          {rows.map((midi) => (
            <g key={midi}>
              <line
                x1={CHART_PAD.left}
                x2={CHART_W - CHART_PAD.right}
                y1={y(midi)}
                y2={y(midi)}
                stroke="var(--border-strong)"
                strokeOpacity={midi % 12 === 0 ? 0.9 : 0.35}
                strokeWidth={1}
              />
              {(midi - low - 1) % labelEvery === 0 && (
                <text
                  x={CHART_PAD.left - 6}
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
              y={CHART_H - 6}
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
                fill={CHART_SONG_COLOR}
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
                fill={CHART_NOTES_COLOR}
              />
            ))}
          {show('voz') && path && (
            <path
              d={path}
              fill="none"
              stroke={CHART_VOICE_COLOR}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}

          {hoverT !== null && (
            <line
              x1={x(hoverT)}
              x2={x(hoverT)}
              y1={CHART_PAD.top}
              y2={CHART_H - CHART_PAD.bottom}
              stroke="var(--text-base-soft)"
              strokeWidth={1}
            />
          )}
        </svg>

        {hover && hoverT !== null && (
          <MelodyChartTooltip
            hoverT={hoverT}
            posX={x(hoverT)}
            voice={hover.voice}
            detected={hover.detected}
            song={hover.song}
          />
        )}
      </div>

      <p className="text-xs text-muted">
        La línea es la altura real de tu voz; las barras naranjas, las notas detectadas; y las
        azules, la melodía ajustada al pulso.
      </p>
    </section>
  )
}
