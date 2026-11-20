export interface LyricsLine {
  text: string
  type: 'lyric' | 'section' | 'cue'
  startTime: number
}

const SECONDS_PER_LINE = 4.5
const INTRO_SECONDS = 8

export function parseLyrics(text: string, audioDuration: number): LyricsLine[] {
  const raw = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  const lines: LyricsLine[] = raw.map((t) => ({
    text: t,
    type: /^\[.+\]$/.test(t) ? 'section' : /^\(.+\)$/.test(t) ? 'cue' : 'lyric',
    startTime: -1,
  }))

  const introTime = Math.min(INTRO_SECONDS, audioDuration * 0.08)
  let lyricIdx = 0

  const timed = lines.map((line) => {
    if (line.type !== 'lyric') {
      return line
    }
    const startTime = introTime + lyricIdx * SECONDS_PER_LINE
    lyricIdx += 1
    return { ...line, startTime }
  })

  for (let i = 0; i < timed.length; i += 1) {
    if (timed[i].type !== 'lyric') {
      let nextLyricTime = introTime
      for (let j = i + 1; j < timed.length; j += 1) {
        if (timed[j].type === 'lyric') {
          nextLyricTime = timed[j].startTime
          break
        }
      }
      timed[i] = { ...timed[i], startTime: nextLyricTime }
    }
  }

  return timed
}
