import { CHART_W, hz, noteName } from '../lib/melody-chart-geometry'

export type ChartSeriesKey = 'voz' | 'notas' | 'cancion'

export const CHART_SONG_COLOR = '#3b82f6'
export const CHART_NOTES_COLOR = 'var(--color-primary)'
export const CHART_VOICE_COLOR = 'var(--text-base)'

const SERIES: { key: ChartSeriesKey; label: string }[] = [
  { key: 'voz', label: 'Tu voz' },
  { key: 'notas', label: 'Notas detectadas' },
  { key: 'cancion', label: 'Melodía de la canción' },
]

export function MelodyChartLegend({
  show,
  onToggle,
}: {
  show: (key: ChartSeriesKey) => boolean
  onToggle: (key: ChartSeriesKey) => void
}) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Mostrar u ocultar series">
      {SERIES.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => onToggle(item.key)}
          aria-pressed={show(item.key)}
          className="inline-flex items-center gap-2 rounded-full border border-border-strong px-3 py-1 text-xs"
          style={{ color: show(item.key) ? 'var(--text-base)' : 'var(--text-base-muted)' }}
        >
          {item.key === 'voz' ? (
            <span className="h-0.5 w-4 rounded" style={{ background: CHART_VOICE_COLOR }} />
          ) : (
            <span
              className="w-4 rounded-sm"
              style={{
                height: item.key === 'cancion' ? 8 : 4,
                background: item.key === 'cancion' ? CHART_SONG_COLOR : CHART_NOTES_COLOR,
                opacity: show(item.key) ? 1 : 0.4,
              }}
            />
          )}
          {item.label}
        </button>
      ))}
    </div>
  )
}

export function MelodyChartTooltip({
  hoverT,
  posX,
  voice,
  detected,
  song,
}: {
  hoverT: number
  posX: number
  voice: number | null
  detected?: [number, number, number]
  song?: [number, number, number]
}) {
  return (
    <div
      className="pointer-events-none absolute top-1 flex flex-col gap-0.5 whitespace-nowrap rounded-md border border-border-strong bg-surface px-2 py-1 text-xs text-white"
      style={{
        left: `${(posX / CHART_W) * 100}%`,
        transform: posX > CHART_W * 0.6 ? 'translateX(calc(-100% - 8px))' : 'translateX(8px)',
      }}
    >
      <span className="text-muted">{hoverT.toFixed(1)} s</span>
      <span>Tu voz: {voice === null ? '—' : `${noteName(voice)} · ${hz(voice)} Hz`}</span>
      <span>Detectada: {detected ? `${noteName(detected[0])} · ${hz(detected[0])} Hz` : '—'}</span>
      <span>Canción: {song ? `${noteName(song[0])} · ${hz(song[0])} Hz` : '—'}</span>
    </div>
  )
}
