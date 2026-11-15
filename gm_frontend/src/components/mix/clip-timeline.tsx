import type { MixClip } from '../../api/modules/mix.api'

interface ClipTimelineProps {
  clips: MixClip[]
  selectedClipId: string | null
  onSelectClip: (id: string) => void
}

export default function ClipTimeline({ clips, selectedClipId, onSelectClip }: ClipTimelineProps) {
  if (clips.length === 0) {
    return (
      <div
        style={{
          height: 72,
          borderRadius: 8,
          background: 'var(--bg-card-hover)',
          border: '2px dashed var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span style={{ fontSize: 13, color: 'var(--text-subdued)' }}>
          Agrega clips desde la biblioteca para armar tu mix
        </span>
      </div>
    )
  }

  const totalMs = clips.reduce((acc, c) => acc + c.duration_ms, 0)

  const sortedClips = clips.slice().sort((a, b) => a.position - b.position)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: 'var(--text-subdued)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          Timeline · {sortedClips.length} clips
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-subdued)' }}>
          Selecciona un clip para editarlo
        </span>
      </div>

      {/* Timeline bar */}
      <div style={{ overflowX: 'auto', paddingBottom: 2 }}>
        <div
          style={{
            display: 'flex',
            gap: 3,
            height: 48,
            minWidth: 'max(100%, 520px)',
            borderRadius: 8,
            overflow: 'hidden',
          }}
        >
          {sortedClips.map((clip, idx) => {
            const widthPct = totalMs > 0 ? (clip.duration_ms / totalMs) * 100 : 100 / clips.length
            const isSelected = clip.id === selectedClipId
            const colors = [
              'var(--color-primary)',
              'var(--color-primary-deep)',
              'var(--color-primary-deep)',
              'var(--color-primary-deep)',
              'var(--color-primary-deep)',
              'var(--color-primary-hover)',
              'var(--color-primary-deep)',
              'var(--color-primary-deep)',
            ]
            const color = colors[idx % colors.length]

            return (
              <button
                key={clip.id}
                onClick={() => onSelectClip(clip.id)}
                type="button"
                aria-pressed={isSelected}
                aria-label={`Seleccionar clip ${clip.position + 1}: ${clip.song_detail?.title ?? 'Sin título'}`}
                title={`Clip ${clip.position + 1}: ${clip.song_detail?.title ?? 'Sin título'} (${Math.round(clip.duration_ms / 1000)}s)`}
                style={{
                  appearance: 'none',
                  width: `${widthPct}%`,
                  minWidth: 32,
                  background: isSelected ? 'var(--text-base)' : color,
                  opacity: isSelected ? 1 : 0.8,
                  borderRadius: 4,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.15s',
                  border: isSelected ? '2px solid var(--text-base)' : '2px solid transparent',
                  overflow: 'hidden',
                  flexShrink: 0,
                  padding: 0,
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: isSelected ? color : 'var(--text-base)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    padding: '0 6px',
                  }}
                >
                  {idx + 1}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Duration labels */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 11,
          color: 'var(--text-subdued)',
        }}
      >
        <span>0:00</span>
        <span>
          {Math.floor(totalMs / 60000)}:
          {String(Math.floor((totalMs % 60000) / 1000)).padStart(2, '0')}
        </span>
      </div>
    </div>
  )
}
