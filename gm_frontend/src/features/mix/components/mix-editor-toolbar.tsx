import { ArrowLeft, Check, Download, Pause, Play, UploadCloud } from 'lucide-react'

import { Button } from '../../../components/ui'

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
    <div className="flex min-w-0 shrink-0 flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={onBack}
        aria-label="Volver a Mix"
        className="inline-flex items-center gap-1.5 py-1 text-xs font-semibold text-muted transition-colors hover:text-white"
      >
        <ArrowLeft size={14} aria-hidden="true" />
        Mix
      </button>

      <div className="h-4 w-px bg-border" aria-hidden="true" />

      {editingTitle ? (
        <input
          value={titleDraft}
          onChange={(e) => onTitleChange(e.target.value)}
          onBlur={onSaveTitle}
          onKeyDown={(e) => e.key === 'Enter' && onSaveTitle()}
          autoFocus
          aria-label="Nombre del proyecto"
          className="min-w-[180px] max-w-[340px] border-b-2 border-primary bg-transparent text-lg font-bold text-white outline-none"
        />
      ) : (
        <button
          type="button"
          onClick={onStartEditing}
          title="Haz clic para editar el título"
          className="max-w-[340px] cursor-text truncate text-lg font-bold text-white hover:text-primary"
        >
          {title}
        </button>
      )}

      {bpm && <span className="text-xs text-muted">{bpm} BPM</span>}

      <span
        className="hidden items-center gap-1 rounded-full bg-card-hover px-2.5 py-1 text-[11px] text-muted sm:inline-flex"
        title="Tus cambios en la línea de tiempo se guardan automáticamente"
      >
        <Check size={12} className="text-success" aria-hidden="true" />
        Guardado automático
      </span>

      <div className="flex-1" />

      {showPlaybackControl && (
        <button
          type="button"
          onClick={onTogglePlayback}
          disabled={!canPlay}
          aria-label={isPlaying ? 'Pausar mix' : 'Reproducir mix'}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border bg-card-hover text-muted hover:text-white disabled:cursor-not-allowed disabled:opacity-45"
        >
          {isPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
        </button>
      )}

      <Button
        variant="secondary"
        size="sm"
        costCredits={3}
        leftIcon={<UploadCloud size={14} />}
        onClick={onSave}
      >
        Publicar en Biblioteca
      </Button>

      <Button
        variant="primary"
        size="sm"
        costCredits={3}
        leftIcon={<Download size={14} />}
        onClick={onExport}
      >
        Exportar audio
      </Button>
    </div>
  )
}
