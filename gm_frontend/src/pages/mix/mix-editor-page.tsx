import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getMixProject,
  updateMixProject,
  updateClip,
  splitClip,
  deleteClip,
  startMixExport,
} from '../../api/modules/mix.api'
import type { MixProject, MixClip } from '../../api/modules/mix.api'
import { useMixExport } from '../../hooks/useMixExport'
import useMixPlayback from '../../hooks/useMixPlayback'
import ClipTimeline from '../../components/mix/clip-timeline'
import ClipCard from '../../components/mix/clip-card'
import ClipInspector, { type ClipField } from '../../components/mix/clip-inspector'
import ClipActions from '../../components/mix/clip-actions'
import AddClipModal from '../../components/mix/add-clip-modal'
import SaveMixModal from '../../components/mix/save-mix-modal'
import MixEditorToolbar from '../../components/mix/mix-editor-toolbar'
import MixTransport from '../../components/mix/mix-transport'
import styles from './mix-editor-page.module.css'

interface ExportState {
  mutedClipIds: string[]
  soloClipIds: string[]
}

function ExportModal({
  mixId,
  exportState,
  onClose,
}: {
  mixId: string
  exportState: ExportState
  onClose: () => void
}) {
  const [format, setFormat] = useState<'mp3' | 'wav'>('mp3')
  const [quality, setQuality] = useState('320k')
  const [exportId, setExportId] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const { status, downloadUrl, error } = useMixExport(exportId)

  async function handleExport() {
    setStarting(true)
    try {
      const res = await startMixExport(mixId, {
        format,
        quality,
        muted_clip_ids: exportState.mutedClipIds,
        solo_clip_ids: exportState.soloClipIds,
      })
      setExportId(res.export_id)
    } catch {
      setStarting(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 300,
        background: 'var(--overlay)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 360,
          background: 'var(--bg-surface)',
          borderRadius: 12,
          border: '1px solid var(--border)',
          padding: 24,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Exportar mix</h3>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-subdued)',
              fontSize: 20,
            }}
          >
            ×
          </button>
        </div>

        {!exportId ? (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
              <label
                style={{
                  fontSize: 13,
                  color: 'var(--text-subdued)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                }}
              >
                Formato
                <select
                  value={format}
                  onChange={(e) => setFormat(e.target.value as 'mp3' | 'wav')}
                  style={{
                    background: 'var(--bg-card-hover)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    color: 'var(--text-base)',
                    fontSize: 14,
                  }}
                >
                  <option value="mp3">MP3</option>
                  <option value="wav">WAV (lossless)</option>
                </select>
              </label>
              {format === 'mp3' && (
                <label
                  style={{
                    fontSize: 13,
                    color: 'var(--text-subdued)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}
                >
                  Calidad
                  <select
                    value={quality}
                    onChange={(e) => setQuality(e.target.value)}
                    style={{
                      background: 'var(--bg-card-hover)',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      padding: '8px 12px',
                      color: 'var(--text-base)',
                      fontSize: 14,
                    }}
                  >
                    <option value="128k">128 kbps</option>
                    <option value="320k">320 kbps (recomendado)</option>
                  </select>
                </label>
              )}
            </div>
            <button
              onClick={handleExport}
              disabled={starting}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 700,
                background: 'var(--gradient-primary)',
                color: 'var(--text-base)',
                border: 'none',
                cursor: 'pointer',
                opacity: starting ? 0.6 : 1,
              }}
            >
              {starting ? 'Iniciando...' : 'Exportar (3 créditos)'}
            </button>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '10px 0' }}>
            {status === 'ready' && downloadUrl ? (
              <>
                <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
                <p style={{ color: 'var(--color-success)', fontWeight: 700, marginBottom: 16 }}>
                  ¡Mix listo!
                </p>
                <a
                  href={downloadUrl}
                  download
                  style={{
                    display: 'block',
                    padding: '12px',
                    borderRadius: 8,
                    background: 'var(--gradient-primary)',
                    color: 'var(--text-base)',
                    fontWeight: 700,
                    fontSize: 14,
                    textDecoration: 'none',
                  }}
                >
                  ⬇ Descargar {format.toUpperCase()}
                </a>
              </>
            ) : status === 'failed' ? (
              <>
                <p style={{ color: 'var(--color-error)', marginBottom: 12 }}>
                  Error al exportar: {error}
                </p>
                <button
                  onClick={() => setExportId(null)}
                  style={{
                    background: 'var(--bg-card-hover)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '10px 20px',
                    cursor: 'pointer',
                    color: 'var(--text-base)',
                  }}
                >
                  Reintentar
                </button>
              </>
            ) : (
              <div
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    border: '3px solid var(--color-primary)',
                    borderTop: '3px solid transparent',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite',
                  }}
                />
                <p style={{ color: 'var(--text-subdued)', fontSize: 14 }}>Procesando tu mix...</p>
              </div>
            )}
          </div>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

export default function MixEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [mix, setMix] = useState<MixProject | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [showSave, setShowSave] = useState(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const playback = useMixPlayback(mix?.clips ?? [])

  useEffect(() => {
    if (!id) {
      return
    }
    getMixProject(id)
      .then((m) => {
        setMix(m)
        setTitleDraft(m.title)
      })
      .finally(() => setLoading(false))
  }, [id])

  async function saveTitle() {
    if (!mix || !titleDraft.trim() || titleDraft === mix.title) {
      setEditingTitle(false)
      return
    }
    const updated = await updateMixProject(mix.id, { title: titleDraft.trim() })
    setMix(updated)
    setEditingTitle(false)
  }

  function handleClipAdded(clip: MixClip) {
    if (!mix) {
      return
    }
    setMix((prev) =>
      prev ? { ...prev, clips: [...prev.clips, clip], clip_count: prev.clip_count + 1 } : prev
    )
    setSelectedClipId(clip.id)
    playback.setTimelinePosition(clip.timeline_start_ms)
    setShowAddModal(false)
  }

  function handleSelectClip(clipId: string) {
    setSelectedClipId(clipId)
    const clip = mix?.clips.find((item) => item.id === clipId)
    if (clip && playback.playbackState !== 'playing') {
      playback.setTimelinePosition(clip.timeline_start_ms)
    }
  }

  function handleClipUpdated(updated: MixClip) {
    if (!mix) {
      return
    }
    setMix((prev) =>
      prev ? { ...prev, clips: prev.clips.map((c) => (c.id === updated.id ? updated : c)) } : prev
    )
  }

  function handleClipPositionPreview(clipId: string, timelineStartMs: number) {
    setMix((prev) =>
      prev
        ? {
            ...prev,
            clips: prev.clips.map((clip) =>
              clip.id === clipId ? { ...clip, timeline_start_ms: timelineStartMs } : clip
            ),
          }
        : prev
    )
  }

  async function handleClipPositionCommit(
    clipId: string,
    timelineStartMs: number,
    initialTimelineStartMs: number
  ) {
    if (!mix) {
      return
    }

    try {
      const updated = await updateClip(mix.id, clipId, { timeline_start_ms: timelineStartMs })
      handleClipUpdated(updated)
    } catch {
      setMix((prev) =>
        prev
          ? {
              ...prev,
              clips: prev.clips.map((clip) =>
                clip.id === clipId ? { ...clip, timeline_start_ms: initialTimelineStartMs } : clip
              ),
            }
          : prev
      )
    }
  }

  async function handleRightClipUpdate(clipId: string, field: ClipField, value: number) {
    if (!mix) {
      return
    }
    const updated = await updateClip(mix.id, clipId, { [field]: value })
    handleClipUpdated(updated)
  }

  async function handleMuteToggle(clipId: string) {
    if (!mix) {
      return
    }
    const nextValue = !playback.mutedClipIds[clipId]
    playback.toggleMute(clipId)
    try {
      const updated = await updateClip(mix.id, clipId, { is_muted: nextValue })
      handleClipUpdated(updated)
    } catch {
      playback.toggleMute(clipId)
    }
  }

  async function handleSoloToggle(clipId: string) {
    if (!mix) {
      return
    }
    const nextValue = !playback.soloClipIds[clipId]
    playback.toggleSolo(clipId)
    try {
      const updated = await updateClip(mix.id, clipId, { is_solo: nextValue })
      handleClipUpdated(updated)
    } catch {
      playback.toggleSolo(clipId)
    }
  }

  async function handleClipSplit(clipId = selectedClipId) {
    if (!mix || !clipId) {
      return
    }
    const result = await splitClip(mix.id, clipId, playback.timelinePositionMs)
    setMix((prev) => {
      if (!prev) {
        return prev
      }
      const leftPosition = result.left_clip.position
      const clips = prev.clips
        .filter((clip) => clip.id !== result.left_clip.id)
        .map((clip) =>
          clip.position > leftPosition ? { ...clip, position: clip.position + 1 } : clip
        )
      return {
        ...prev,
        clips: [...clips, result.left_clip, result.right_clip],
        clip_count: prev.clip_count + 1,
      }
    })
    setSelectedClipId(result.right_clip.id)
    playback.setTimelinePosition(result.right_clip.timeline_start_ms)
  }

  async function handleSelectedClipDelete(clipId: string) {
    if (!mix) {
      return
    }
    await deleteClip(mix.id, clipId)
    handleClipDeleted(clipId)
  }

  function handleClipDeleted(clipId: string) {
    if (!mix) {
      return
    }
    playback.removeClipFromPlayback(clipId)
    setMix((prev) =>
      prev
        ? {
            ...prev,
            clips: prev.clips.filter((c) => c.id !== clipId),
            clip_count: Math.max(0, prev.clip_count - 1),
          }
        : prev
    )
    if (selectedClipId === clipId) {
      setSelectedClipId(null)
      playback.stopPlayback()
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '28px 32px', color: 'var(--text-subdued)', fontSize: 14 }}>
        Cargando editor...
      </div>
    )
  }

  if (!mix) {
    return (
      <div style={{ padding: '28px 32px', color: 'var(--text-base)' }}>
        <p style={{ color: 'var(--color-error)' }}>Proyecto no encontrado.</p>
        <button
          onClick={() => navigate('/mix')}
          style={{
            marginTop: 12,
            color: 'var(--color-primary)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: 14,
          }}
        >
          ← Volver a Mix
        </button>
      </div>
    )
  }

  const sortedClips = [...mix.clips].sort((a, b) => a.position - b.position)

  return (
    <div className={styles.editorPage}>
      <MixEditorToolbar
        title={mix.title}
        titleDraft={titleDraft}
        editingTitle={editingTitle}
        bpm={mix.bpm}
        isPlaying={playback.playbackState === 'playing'}
        canPlay={false}
        showPlaybackControl={false}
        onBack={() => navigate('/mix')}
        onStartEditing={() => setEditingTitle(true)}
        onTitleChange={setTitleDraft}
        onSaveTitle={() => void saveTitle()}
        onTogglePlayback={playback.toggleGlobalPlayback}
        onSave={() => setShowSave(true)}
        onExport={() => setShowExport(true)}
      />

      {/* Timeline */}
      <div className={styles.timeline}>
        <MixTransport
          playbackState={playback.playbackState}
          positionMs={playback.timelinePositionMs}
          totalDurationMs={playback.totalDurationMs}
          onTogglePlayback={playback.toggleGlobalPlayback}
          onRestart={playback.restartGlobalPlayback}
          onStop={playback.stopPlayback}
        />
        <ClipTimeline
          clips={sortedClips}
          selectedClipId={selectedClipId}
          onSelectClip={handleSelectClip}
          onContextSelectClip={setSelectedClipId}
          onPreviewPosition={handleClipPositionPreview}
          onCommitPosition={(clipId, timelineStartMs, initialTimelineStartMs) =>
            void handleClipPositionCommit(clipId, timelineStartMs, initialTimelineStartMs)
          }
          playheadMs={playback.timelinePositionMs}
          onPlayheadChange={playback.setTimelinePosition}
          playingClipId={playback.playingClipId}
          playbackState={playback.playbackState}
          playbackMode={playback.playbackMode}
          mutedClipIds={playback.mutedClipIds}
          soloClipIds={playback.soloClipIds}
          onToggleClipPlayback={playback.toggleClipPlayback}
          onToggleMute={(clipId) => void handleMuteToggle(clipId)}
          onToggleSolo={(clipId) => void handleSoloToggle(clipId)}
          onSplitClip={(clipId) => handleClipSplit(clipId)}
          onDeleteClip={(clipId) => handleSelectedClipDelete(clipId)}
          onAddClip={() => setShowAddModal(true)}
        />
      </div>

      {/* Editor body: library column + clips column */}
      <div className={styles.editorBody}>
        {/* Selected clip detail */}
        <div className={styles.inspector}>
          {selectedClipId ? (
            (() => {
              const clip = mix.clips.find((c) => c.id === selectedClipId)
              if (!clip) {
                return null
              }
              return (
                <>
                  <ClipCard
                    clip={clip}
                    mixId={mix.id}
                    isSelected
                    onSelect={() => handleSelectClip(clip.id)}
                    onDelete={() => handleClipDeleted(clip.id)}
                    isPlaying={
                      playback.playbackState === 'playing' &&
                      (playback.playingClipId === clip.id ||
                        (playback.playbackMode === 'global' &&
                          playback.timelinePositionMs >= clip.timeline_start_ms &&
                          playback.timelinePositionMs < clip.timeline_start_ms + clip.duration_ms))
                    }
                    timelinePositionMs={playback.timelinePositionMs}
                    muted={Boolean(playback.mutedClipIds[clip.id])}
                    solo={Boolean(playback.soloClipIds[clip.id])}
                    onTogglePlay={() => {
                      handleSelectClip(clip.id)
                      playback.toggleClipPlayback(clip.id)
                    }}
                    onToggleMute={() => void handleMuteToggle(clip.id)}
                    onToggleSolo={() => void handleSoloToggle(clip.id)}
                  />
                  <ClipInspector
                    clip={clip}
                    onUpdate={(field, value) => handleRightClipUpdate(clip.id, field, value)}
                  />
                  <ClipActions
                    clip={clip}
                    playheadMs={playback.timelinePositionMs}
                    onSplit={handleClipSplit}
                    showDelete={false}
                  />
                </>
              )
            })()
          ) : (
            <div
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-subdued)',
                textAlign: 'center',
                gap: 12,
              }}
            >
              <svg
                width="36"
                height="36"
                viewBox="0 0 24 24"
                fill="currentColor"
                style={{ opacity: 0.4 }}
              >
                <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
              </svg>
              <p style={{ fontSize: 14 }}>
                Selecciona un clip de la izquierda para editar sus parámetros
              </p>
            </div>
          )}
        </div>
      </div>

      {showAddModal && (
        <AddClipModal
          mixId={mix.id}
          nextPosition={sortedClips.length}
          onAdd={handleClipAdded}
          onClose={() => setShowAddModal(false)}
        />
      )}

      {showExport && (
        <ExportModal
          mixId={mix.id}
          exportState={{
            mutedClipIds: Object.keys(playback.mutedClipIds).filter(
              (clipId) => playback.mutedClipIds[clipId]
            ),
            soloClipIds: Object.keys(playback.soloClipIds).filter(
              (clipId) => playback.soloClipIds[clipId]
            ),
          }}
          onClose={() => setShowExport(false)}
        />
      )}

      {showSave && (
        <SaveMixModal
          mix={mix}
          exportState={{
            mutedClipIds: Object.keys(playback.mutedClipIds).filter(
              (clipId) => playback.mutedClipIds[clipId]
            ),
            soloClipIds: Object.keys(playback.soloClipIds).filter(
              (clipId) => playback.soloClipIds[clipId]
            ),
          }}
          onClose={() => setShowSave(false)}
          onRenamed={(updated) => setMix(updated)}
        />
      )}
    </div>
  )
}
