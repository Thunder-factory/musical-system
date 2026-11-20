import {
  INSPIRATION_SCALES,
  INSPIRATION_STYLES,
  type InspirationStyle,
} from './inspiration-styles'

export { INSPIRATION_STYLES }
export type { InspirationStyle }

export interface MelodyNote {
  midi: number
  start: number
  duration: number
}

export interface Melody {
  style: InspirationStyle
  bpm: number
  tonic: number
  notes: MelodyNote[]
  beats: number
}

function random(seed: number) {
  let t = seed >>> 0
  return () => {
    t += 0x6d2b79f5
    let r = Math.imul(t ^ (t >>> 15), 1 | t)
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r)
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296
  }
}

function pick<T>(rnd: () => number, items: T[]): T {
  return items[Math.floor(rnd() * items.length)]
}

export function generateMelody(style: InspirationStyle, seed: number): Melody {
  const rnd = random(seed)
  const steps = INSPIRATION_SCALES[style.scale]
  const bpm = Math.round(style.bpm[0] + rnd() * (style.bpm[1] - style.bpm[0]))
  const tonic = 55 + Math.floor(rnd() * 6)
  const degreeToMidi = (degree: number) => {
    const octave = Math.floor(degree / steps.length)
    const index = ((degree % steps.length) + steps.length) % steps.length
    return tonic + 12 * octave + steps[index]
  }

  const maxDegree = steps.length
  let degree = Math.floor(rnd() * 3)
  const phrase: MelodyNote[] = []
  let beat = 0
  for (let bar = 0; bar < 2; bar += 1) {
    const rhythm = pick(rnd, style.rhythms)
    for (const duration of rhythm) {
      const leap = rnd() < style.leapiness
      const move = leap ? pick(rnd, [-3, -2, 2, 3]) : pick(rnd, [-1, -1, 0, 1, 1, 1])
      degree = Math.max(0, Math.min(maxDegree, degree + move))
      phrase.push({ midi: degreeToMidi(degree), start: beat, duration })
      beat += duration
    }
  }

  const answer = phrase.map((note) => ({ ...note, start: note.start + 8 }))
  const last = answer[answer.length - 1]
  last.midi = degreeToMidi(rnd() < 0.5 ? 0 : maxDegree)
  if (answer.length > 2) {
    answer[answer.length - 2].midi = degreeToMidi(rnd() < 0.5 ? 1 : 2)
  }

  return { style, bpm, tonic, notes: [...phrase, ...answer], beats: 16 }
}

export function melodySeconds(melody: Melody): number {
  return (melody.beats * 60) / melody.bpm
}

export function midiToName(midi: number): string {
  const names = ['Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si']
  return `${names[midi % 12]}${Math.floor(midi / 12) - 1}`
}

export function playMelody(
  melody: Melody,
  onNote?: (index: number) => void,
  onEnd?: () => void
): () => void {
  const AudioCtx =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  const ctx = new AudioCtx()
  const secondsPerBeat = 60 / melody.bpm
  const start = ctx.currentTime + 0.15
  const master = ctx.createGain()
  master.gain.value = 0.25
  master.connect(ctx.destination)

  melody.notes.forEach((note) => {
    const t0 = start + note.start * secondsPerBeat
    const t1 = t0 + note.duration * secondsPerBeat * 0.92
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'triangle'
    osc.frequency.value = 440 * 2 ** ((note.midi - 69) / 12)
    gain.gain.setValueAtTime(0.0001, t0)
    gain.gain.exponentialRampToValueAtTime(1, t0 + 0.03)
    gain.gain.exponentialRampToValueAtTime(0.0001, t1)
    osc.connect(gain).connect(master)
    osc.start(t0)
    osc.stop(t1 + 0.02)
  })

  for (let beat = 0; beat < melody.beats; beat += 1) {
    const t = start + beat * secondsPerBeat
    const click = ctx.createOscillator()
    const gain = ctx.createGain()
    click.frequency.value = beat % 4 === 0 ? 1500 : 1000
    gain.gain.setValueAtTime(0.15, t)
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.04)
    click.connect(gain).connect(master)
    click.start(t)
    click.stop(t + 0.05)
  }

  const timers = melody.notes.map((note, index) =>
    window.setTimeout(() => onNote?.(index), (0.15 + note.start * secondsPerBeat) * 1000)
  )
  const endTimer = window.setTimeout(
    () => {
      onNote?.(-1)
      onEnd?.()
      ctx.close().catch(() => undefined)
    },
    (0.3 + melody.beats * secondsPerBeat) * 1000
  )

  return () => {
    timers.forEach(window.clearTimeout)
    window.clearTimeout(endTimer)
    onNote?.(-1)
    ctx.close().catch(() => undefined)
  }
}
