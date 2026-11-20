import { useState } from 'react'
import { Music2 } from 'lucide-react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { Button } from '../../../components/ui'
import AddClipModal from '../components/add-clip-modal'
import ClipActions from '../components/clip-actions'
import ClipCard from '../components/clip-card'
import ClipInspector from '../components/clip-inspector'
import ClipTimeline from '../components/clip-timeline'
import ExportMixModal from '../components/export-mix-modal'
import MixEditorToolbar from '../components/mix-editor-toolbar'
import MixTransport from '../components/mix-transport'
import SaveMixModal from '../components/save-mix-modal'
import { useMixEditorState } from '../hooks/useMixEditorState'
import styles from './mix-editor-page.module.css'

export default function MixEditorPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const addSongId = searchParams.get('addSongId')
  const navigate = useNavigate()

  const [showAddModal, setShowAddModal] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [showSave, setShowSave] = useState(false)

  const state = useMixEditorState(id, addSongId)
  const { mix, loading, selectedClipId, playback } = state

  if (loading) {
    return <div className="px-8 py-7 text-sm text-muted">Cargando editor...</div>
  }

  if (!mix) {
    return (
      <div className="space-y-3 px-8 py-7 text-white">
        <p className="text-sm text-error">Proyecto no encontrado.</p>
        <Button variant="secondary" size="sm" onClick={() => navigate('/mix')}>
          ← Volver a Mix
        </Button>
      </div>
    )
  }

  const sortedClips = [...mix.clips].sort((a, b) => a.position - b.position)
  const selectedClip = selectedClipId ? mix.clips.find((c) => c.id === selectedClipId) : null
  const exportState = {
    mutedClipIds: Object.keys(playback.mutedClipIds).filter((cid) => playback.mutedClipIds[cid]),
    soloClipIds: Object.keys(playback.soloClipIds).filter((cid) => playback.soloClipIds[cid]),
  }

  return (
    <div className={styles.editorPage}>
      <MixEditorToolbar
        title={mix.title}
        titleDraft={state.titleDraft}
        editingTitle={state.editingTitle}
        bpm={mix.bpm}
        isPlaying={playback.playbackState === 'playing'}
        canPlay={false}
        showPlaybackControl={false}
        onBack={() => navigate('/mix')}
        onStartEditing={() => state.setEditingTitle(true)}
        onTitleChange={state.setTitleDraft}
        onSaveTitle={() => void state.saveTitle()}
        onTogglePlayback={playback.toggleGlobalPlayback}
        onSave={() => setShowSave(true)}
        onExport={() => setShowExport(true)}
      />

      <div className={styles.timeline}>
        <MixTransport
          playbackState={playback.playbackState}
          positionMs={playback.timelinePositionMs}
          totalDurationMs={playback.totalDurationMs}
          onTogglePlayback={playback.toggleGlobalPlayback}
          onRestart={playback.restartGlobalPlayback}
          onStop={playback.stopPlayback}
          playbackError={playback.playbackError}
        />
        <ClipTimeline
          clips={sortedClips}
          selectedClipId={selectedClipId}
          onSelectClip={state.handleSelectClip}
          onContextSelectClip={state.setSelectedClipId}
          onPreviewPosition={state.handleClipPositionPreview}
          onCommitPosition={(clipId, startMs, initMs) =>
            void state.handleClipPositionCommit(clipId, startMs, initMs)
          }
          playheadMs={playback.timelinePositionMs}
          onPlayheadChange={playback.setTimelinePosition}
          playingClipId={playback.playingClipId}
          playbackState={playback.playbackState}
          playbackMode={playback.playbackMode}
          mutedClipIds={playback.mutedClipIds}
          soloClipIds={playback.soloClipIds}
          onToggleClipPlayback={playback.toggleClipPlayback}
          onToggleMute={(cid) => void state.handleMuteToggle(cid)}
          onToggleSolo={(cid) => void state.handleSoloToggle(cid)}
          onSplitClip={(cid) => state.handleClipSplit(cid)}
          onDeleteClip={(cid) => state.handleSelectedClipDelete(cid)}
          onAddClip={() => setShowAddModal(true)}
        />
      </div>

      <div className={styles.editorBody}>
        <div className={styles.inspector}>
          {selectedClip ? (
            <>
              <ClipCard
                clip={selectedClip}
                mixId={mix.id}
                isSelected
                onSelect={() => state.handleSelectClip(selectedClip.id)}
                onDelete={() => state.handleClipDeleted(selectedClip.id)}
                isPlaying={
                  playback.playbackState === 'playing' &&
                  (playback.playingClipId === selectedClip.id ||
                    (playback.playbackMode === 'global' &&
                      playback.timelinePositionMs >= selectedClip.timeline_start_ms &&
                      playback.timelinePositionMs <
                        selectedClip.timeline_start_ms + selectedClip.duration_ms))
                }
                timelinePositionMs={playback.timelinePositionMs}
                muted={Boolean(playback.mutedClipIds[selectedClip.id])}
                solo={Boolean(playback.soloClipIds[selectedClip.id])}
                onTogglePlay={() => {
                  state.handleSelectClip(selectedClip.id)
                  playback.toggleClipPlayback(selectedClip.id)
                }}
                onToggleMute={() => void state.handleMuteToggle(selectedClip.id)}
                onToggleSolo={() => void state.handleSoloToggle(selectedClip.id)}
              />
              <ClipInspector
                clip={selectedClip}
                onUpdate={(field, value) => state.handleRightClipUpdate(selectedClip.id, field, value)}
              />
              <ClipActions
                clip={selectedClip}
                playheadMs={playback.timelinePositionMs}
                onSplit={() => state.handleClipSplit(selectedClip.id)}
                showDelete={false}
              />
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-muted">
              <Music2 size={32} className="opacity-40" aria-hidden="true" />
              <p className="text-sm">Selecciona un clip de arriba para editar sus parámetros</p>
            </div>
          )}
        </div>
      </div>

      <AddClipModal
        open={showAddModal}
        mixId={mix.id}
        nextPosition={sortedClips.length}
        onAdd={(clip) => {
          state.handleClipAdded(clip)
          setShowAddModal(false)
        }}
        onClose={() => setShowAddModal(false)}
      />

      <ExportMixModal
        open={showExport}
        mixId={mix.id}
        mixTitle={mix.title}
        exportState={exportState}
        onClose={() => setShowExport(false)}
      />

      <SaveMixModal
        open={showSave}
        mix={mix}
        exportState={exportState}
        onClose={() => setShowSave(false)}
        onRenamed={(updated) => state.setMix(updated)}
      />
    </div>
  )
}
