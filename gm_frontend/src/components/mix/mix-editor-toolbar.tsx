import { ArrowLeft, Download, Pause, Play, Save } from 'lucide-react'

interface MixEditorToolbarProps {
  title: string
  titleDraft: string
  editingTitle: boolean
  bpm: number | null
  isPlaying: boolean
  canPlay: boolean
  showPlaybackControl?: boolean
  onBack: () => void
  onStartEditing: () => void
  onTitleChange: (value: string) => void
  onSaveTitle: () => void
  onTogglePlayback: () => void
  onSave: () => void
  onExport: () => void
}

export default function MixEditorToolbar({
  title,
  titleDraft,
  editingTitle,
  bpm,
  isPlaying,
  canPlay,
  showPlaybackControl = true,
  onBack,
  onStartEditing,
  onTitleChange,
  onSaveTitle,
  onTogglePlayback,
  onSave,
  onExport,
}: MixEditorToolbarProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0, minWidth: 0 }}>
      <button
        type="button"
        onClick={onBack}
        title="Volver a Mix"
        aria-label="Volver a Mix"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: '6px 0',
          border: 'none',
          background: 'none',
          color: 'var(--text-subdued)',
          cursor: 'pointer',
          fontSize: 13,
        }}
      >
        <ArrowLeft size={14} aria-hidden="true" />
        Mix
      </button>
      <div style={{ width: 1, height: 16, background: 'var(--border)' }} aria-hidden="true" />

      {editingTitle ? (
        <input
          value={titleDraft}
          onChange={(event) => onTitleChange(event.target.value)}
          onBlur={onSaveTitle}
          onKeyDown={(event) => event.key === 'Enter' && onSaveTitle()}
          autoFocus
          aria-label="Nombre del proyecto"
          style={{
            minWidth: 180,
            maxWidth: 360,
            fontSize: 18,
            fontWeight: 700,
            background: 'transparent',
            border: 'none',
            borderBottom: '2px solid var(--color-primary)',
            color: 'var(--text-base)',
            outline: 'none',
          }}
        />
      ) : (
        <button
          type="button"
          onClick={onStartEditing}
          title="Haz clic para editar el título"
          style={{
            maxWidth: 360,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            padding: 0,
            border: 'none',
            background: 'none',
            color: 'var(--text-base)',
            cursor: 'text',
            fontSize: 18,
            fontWeight: 700,
          }}
        >
          {title}
        </button>
      )}

      {bpm && <span style={{ fontSize: 13, color: 'var(--text-subdued)' }}>{bpm} BPM</span>}

      <div style={{ flex: 1 }} />

      {showPlaybackControl && (
        <button
          type="button"
          onClick={onTogglePlayback}
          disabled={!canPlay}
          title={
            canPlay ? (isPlaying ? 'Pausar mix' : 'Reproducir mix') : 'Reproducción no disponible'
          }
          aria-label={
            canPlay ? (isPlaying ? 'Pausar mix' : 'Reproducir mix') : 'Reproducción no disponible'
          }
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 34,
            height: 34,
            padding: 0,
            borderRadius: '50%',
            border: '1px solid var(--border)',
            background: 'var(--bg-card-hover)',
            color: 'var(--text-subdued)',
            cursor: canPlay ? 'pointer' : 'not-allowed',
            opacity: canPlay ? 1 : 0.45,
          }}
        >
          {isPlaying ? (
            <Pause size={15} fill="currentColor" />
          ) : (
            <Play size={15} fill="currentColor" />
          )}
        </button>
      )}

      <button
        type="button"
        onClick={onSave}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '8px 16px',
          borderRadius: 500,
          fontSize: 13,
          fontWeight: 700,
          background: 'none',
          color: 'var(--color-primary)',
          border: '1px solid var(--color-primary)',
          cursor: 'pointer',
        }}
      >
        <Save size={14} aria-hidden="true" />
        Guardar
      </button>

      <button
        type="button"
        onClick={onExport}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '8px 16px',
          borderRadius: 500,
          fontSize: 13,
          fontWeight: 700,
          background: 'var(--gradient-primary)',
          color: 'var(--text-base)',
          border: 'none',
          cursor: 'pointer',
        }}
      >
        <Download size={14} aria-hidden="true" />
        Exportar
      </button>
    </div>
  )
}
