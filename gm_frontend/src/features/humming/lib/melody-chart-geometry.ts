import type { HummingChart } from '../api/humming.api'
import { midiToName } from './melody-generator'

export const CHART_W = 640
export const CHART_H = 240
export const CHART_PAD = { left: 44, right: 8, top: 8, bottom: 22 }

export function hz(midi: number) {
  return Math.round(440 * 2 ** ((midi - 69) / 12))
}

export function noteName(midi: number) {
  return midiToName(Math.round(midi))
}

export function noteAt(notes: [number, number, number][], t: number) {
  return notes.find(([, start, dur]) => t >= start && t < start + dur)
}

export function computeChartGeometry(chart: HummingChart) {
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
  const x = (t: number) => CHART_PAD.left + (t / duration) * (CHART_W - CHART_PAD.left - CHART_PAD.right)
  const y = (midi: number) =>
    CHART_PAD.top + ((high - midi) / (high - low)) * (CHART_H - CHART_PAD.top - CHART_PAD.bottom)
  const row = (CHART_H - CHART_PAD.top - CHART_PAD.bottom) / (high - low)

  let path = ''
  let drawing = false
  let previous: number | null = null
  chart.contorno.forEach((value, i) => {
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
}
