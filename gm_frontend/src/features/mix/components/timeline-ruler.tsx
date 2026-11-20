import styles from './clip-timeline.module.css'

interface TimelineRulerProps {
  totalMs: number
  pixelsPerSecond: number
}

function chooseIntervalMs(pixelsPerSecond: number) {
  const targetMs = (45 / pixelsPerSecond) * 1000
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(targetMs, 1)))
  const normalized = targetMs / magnitude
  const multiplier = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  return Math.max(100, multiplier * magnitude)
}

function formatTick(milliseconds: number) {
  if (milliseconds < 1000) {
    return `${milliseconds}ms`
  }
  const seconds = milliseconds / 1000
  if (seconds < 60) {
    return `${seconds % 1 === 0 ? seconds : seconds.toFixed(1)}s`
  }
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}

export default function TimelineRuler({ totalMs, pixelsPerSecond }: TimelineRulerProps) {
  const intervalMs = chooseIntervalMs(pixelsPerSecond)
  const tickCount = Math.ceil(totalMs / intervalMs)
  const labelEvery = intervalMs < 1000 ? Math.max(1, Math.round(1000 / intervalMs)) : 1
  const ticks = Array.from({ length: tickCount + 1 }, (_, index) => index * intervalMs)

  return (
    <div className={styles.ruler} aria-label="Regla temporal">
      {ticks.map((milliseconds, index) => (
        <div
          className={styles.rulerTick}
          key={milliseconds}
          style={{ left: `${Math.min((milliseconds / totalMs) * 100, 100)}%` }}
        >
          <span className={styles.rulerLine} />
          {index % labelEvery === 0 && (
            <span className={styles.rulerLabel}>{formatTick(milliseconds)}</span>
          )}
        </div>
      ))}
    </div>
  )
}
