import { Link } from 'react-router-dom'
import { Library, Upload } from 'lucide-react'

import { cn } from '../../../lib/cn'
import { STEM_CREDIT_COST } from '../api/stems.api'
import AudioUploader from './audio-uploader'
import LibrarySongPicker from './library-song-picker'
import StemProgress from './stem-progress'

export type StemSourceTab = 'library' | 'upload'

interface StemSourcePanelProps {
  sourceTab: StemSourceTab
  selectedSongId: string | null
  balance: number
  insufficientCredits: boolean
  noCreditsApi: boolean
  submitting: boolean
  isProcessing: boolean
  uploaderResetKey: number
  submitError: string | null
  activeJobId: string | null
  status: string | null
  progress: number
  error: string | null
  loadingStatus: boolean
  onTabChange: (tab: StemSourceTab) => void
  onSelectSong: (songId: string) => void
  onFileSelected: () => void
  onSeparateSong: (songId: string, title: string) => void
  onSeparateFile: (file: File) => void
}

export default function StemSourcePanel({
  sourceTab,
  selectedSongId,
  balance,
  insufficientCredits,
  noCreditsApi,
  submitting,
  isProcessing,
  uploaderResetKey,
  submitError,
  activeJobId,
  status,
  progress,
  error,
  loadingStatus,
  onTabChange,
  onSelectSong,
  onFileSelected,
  onSeparateSong,
  onSeparateFile,
}: StemSourcePanelProps) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 rounded-2xl border border-border bg-card p-5">
      <div role="tablist" aria-label="Origen del audio" className="inline-flex w-fit rounded-full bg-card-hover p-1">
        {[
          { id: 'library' as const, label: 'Desde mi Biblioteca', icon: <Library size={14} /> },
          { id: 'upload' as const, label: 'Subir archivo', icon: <Upload size={14} /> },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={sourceTab === tab.id}
            disabled={submitting || isProcessing}
            onClick={() => onTabChange(tab.id)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-semibold transition-colors disabled:opacity-60',
              sourceTab === tab.id ? 'bg-surface text-white' : 'text-muted hover:text-white'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {(insufficientCredits || noCreditsApi) && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-primary-border bg-primary-soft px-4 py-3 text-sm">
          <span className="text-white">
            Necesitas {STEM_CREDIT_COST} créditos (saldo actual: {balance}).
          </span>
          <Link to="/payments" className="font-semibold text-primary underline">
            Recargar créditos
          </Link>
        </div>
      )}

      {sourceTab === 'library' ? (
        <LibrarySongPicker
          selectedSongId={selectedSongId}
          loading={submitting || isProcessing}
          insufficientCredits={insufficientCredits}
          onSelectSong={onSelectSong}
          onSubmit={onSeparateSong}
        />
      ) : (
        <AudioUploader
          onSubmit={onSeparateFile}
          resetKey={uploaderResetKey}
          onFileSelected={onFileSelected}
          loading={submitting || isProcessing}
          insufficientCredits={insufficientCredits}
        />
      )}

      {submitError && (
        <p className="text-sm text-error" role="alert">
          {submitError}
        </p>
      )}

      {activeJobId && (
        <StemProgress status={status} progress={progress} error={error} loadingStatus={loadingStatus} />
      )}
    </div>
  )
}
