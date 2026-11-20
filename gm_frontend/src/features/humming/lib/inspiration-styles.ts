export interface InspirationStyle {
  key: string
  label: string
  bpm: [number, number]
  scale: 'mayor' | 'menor' | 'pentatonica' | 'pentatonica-menor'
  rhythms: number[][]
  leapiness: number
}

export const INSPIRATION_SCALES: Record<InspirationStyle['scale'], number[]> = {
  mayor: [0, 2, 4, 5, 7, 9, 11],
  menor: [0, 2, 3, 5, 7, 8, 10],
  pentatonica: [0, 2, 4, 7, 9],
  'pentatonica-menor': [0, 3, 5, 7, 10],
}

export const INSPIRATION_STYLES: InspirationStyle[] = [
  {
    key: 'pop',
    label: 'Pop',
    bpm: [100, 118],
    scale: 'mayor',
    rhythms: [
      [1, 0.5, 0.5, 1, 1],
      [0.5, 0.5, 1, 1, 1],
      [1, 1, 0.5, 0.5, 1],
    ],
    leapiness: 0.25,
  },
  {
    key: 'balada',
    label: 'Balada',
    bpm: [66, 78],
    scale: 'mayor',
    rhythms: [
      [2, 1, 1],
      [1.5, 0.5, 2],
      [1, 1, 2],
    ],
    leapiness: 0.3,
  },
  {
    key: 'cumbia',
    label: 'Cumbia',
    bpm: [92, 104],
    scale: 'menor',
    rhythms: [
      [0.5, 1, 0.5, 1, 1],
      [0.5, 0.5, 0.5, 0.5, 1, 1],
      [1, 0.5, 0.5, 0.5, 1.5],
    ],
    leapiness: 0.2,
  },
  {
    key: 'rock',
    label: 'Rock',
    bpm: [110, 130],
    scale: 'pentatonica-menor',
    rhythms: [
      [1, 1, 0.5, 0.5, 1],
      [0.5, 0.5, 1, 0.5, 0.5, 1],
    ],
    leapiness: 0.3,
  },
  {
    key: 'lofi',
    label: 'Lo-fi',
    bpm: [72, 86],
    scale: 'pentatonica',
    rhythms: [
      [0.75, 0.25, 1, 2],
      [1, 0.75, 0.25, 2],
    ],
    leapiness: 0.25,
  },
  {
    key: 'huayno',
    label: 'Huayno',
    bpm: [96, 112],
    scale: 'pentatonica-menor',
    rhythms: [
      [0.75, 0.25, 0.5, 0.5, 1, 1],
      [0.5, 0.5, 0.75, 0.25, 2],
    ],
    leapiness: 0.15,
  },
  {
    key: 'caporales',
    label: 'Caporales',
    bpm: [104, 116],
    scale: 'menor',
    rhythms: [
      [0.5, 0.5, 0.75, 0.25, 1, 1],
      [1, 0.75, 0.25, 1, 1],
    ],
    leapiness: 0.2,
  },
  {
    key: 'epico',
    label: 'Épico',
    bpm: [80, 96],
    scale: 'menor',
    rhythms: [
      [1.5, 0.5, 2],
      [1, 1, 1, 1],
    ],
    leapiness: 0.4,
  },
]
