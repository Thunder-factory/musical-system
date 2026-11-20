import { useEffect, useState } from 'react'

import { toast } from '../../../store/toast.store'
import {
  deleteClip,
  getMixProject,
  splitClip,
  updateClip,
  updateMixProject,
  type MixClip,
  type MixProject,
} from '../api/mix.api'
import type { ClipField } from '../components/clip-inspector'
import { attachSongToProjectIfNeeded } from './mix-editor-helpers'
import useMixPlayback from './useMixPlayback'

export function useMixEditorState(id: string | undefined, addSongId: string | null) {
  const [mix, setMix] = useState<MixProject | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const playback = useMixPlayback(mix?.clips ?? [], mix?.id)

  useEffect(() => {
    if (!id) {
      return
    }
    let cancelled = false
    setLoading(true)
    getMixProject(id)
      .then(async (loaded) => {
        if (cancelled) {
          return
        }
        let project = loaded
        try {
          const attached = await attachSongToProjectIfNeeded(loaded, addSongId)
          project = attached.project
          if (attached.addedClipId && !cancelled) {
            setSelectedClipId(attached.addedClipId)
            toast.success(
              'Canción añadida al mix',
              `"${attached.songTitle ?? 'Canción'}" se agregó a la línea de tiempo.`
            )
          }
        } catch {
          toast.error('No se pudo añadir la canción seleccionada')
        }
        if (!cancelled) {
          setMix(project)
          setTitleDraft(project.title)
        }
      })
      .catch(() => !cancelled && toast.error('No se pudo cargar el proyecto'))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [id, addSongId])

  async function saveTitle() {
    if (!mix || !titleDraft.trim() || titleDraft === mix.title) {
      setEditingTitle(false)
      return
    }
    try {
      setMix(await updateMixProject(mix.id, { title: titleDraft.trim() }))
    } catch {
      toast.error('No se pudo guardar el título')
      setTitleDraft(mix.title)
    } finally {
      setEditingTitle(false)
    }
  }

  function handleClipUpdated(updated: MixClip) {
    setMix((prev) =>
      prev ? { ...prev, clips: prev.clips.map((c) => (c.id === updated.id ? updated : c)) } : prev
    )
  }

  function handleClipPositionPreview(clipId: string, timelineStartMs: number) {
    setMix((prev) =>
      prev
        ? {
            ...prev,
            clips: prev.clips.map((c) =>
              c.id === clipId ? { ...c, timeline_start_ms: timelineStartMs } : c
            ),
          }
        : prev
    )
  }

  async function handleClipPositionCommit(clipId: string, startMs: number, initStartMs: number) {
    if (!mix) {
      return
    }
    try {
      handleClipUpdated(await updateClip(mix.id, clipId, { timeline_start_ms: startMs }))
    } catch {
      handleClipPositionPreview(clipId, initStartMs)
      toast.error('No se pudo actualizar la posición del clip')
    }
  }

  async function handleToggleFlag(clipId: string, key: 'is_muted' | 'is_solo') {
    if (!mix) {
      return
    }
    const isMute = key === 'is_muted'
    const nextValue = !(isMute ? playback.mutedClipIds[clipId] : playback.soloClipIds[clipId])
    if (isMute) {
      playback.toggleMute(clipId)
    } else {
      playback.toggleSolo(clipId)
    }
    try {
      handleClipUpdated(await updateClip(mix.id, clipId, { [key]: nextValue }))
    } catch {
      if (isMute) {
        playback.toggleMute(clipId)
      } else {
        playback.toggleSolo(clipId)
      }
    }
  }

  async function handleClipSplit(clipId = selectedClipId) {
    if (!mix || !clipId) {
      return
    }
    const res = await splitClip(mix.id, clipId, playback.timelinePositionMs)
    setMix((prev) => {
      if (!prev) {
        return prev
      }
      const leftPos = res.left_clip.position
      const rest = prev.clips
        .filter((c) => c.id !== res.left_clip.id)
        .map((c) => (c.position > leftPos ? { ...c, position: c.position + 1 } : c))
      return {
        ...prev,
        clips: [...rest, res.left_clip, res.right_clip],
        clip_count: prev.clip_count + 1,
      }
    })
    setSelectedClipId(res.right_clip.id)
    playback.setTimelinePosition(res.right_clip.timeline_start_ms)
  }

  function handleClipDeleted(clipId: string) {
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

  return {
    mix,
    setMix,
    loading,
    selectedClipId,
    setSelectedClipId,
    editingTitle,
    setEditingTitle,
    titleDraft,
    setTitleDraft,
    playback,
    saveTitle,
    handleClipAdded: (clip: MixClip) => {
      setMix((prev) =>
        prev ? { ...prev, clips: [...prev.clips, clip], clip_count: prev.clip_count + 1 } : prev
      )
      setSelectedClipId(clip.id)
      playback.setTimelinePosition(clip.timeline_start_ms)
    },
    handleSelectClip: (clipId: string) => {
      setSelectedClipId(clipId)
      const clip = mix?.clips.find((item) => item.id === clipId)
      if (clip && playback.playbackState !== 'playing') {
        playback.setTimelinePosition(clip.timeline_start_ms)
      }
    },
    handleClipPositionPreview,
    handleClipPositionCommit,
    handleRightClipUpdate: async (clipId: string, field: ClipField, value: number) => {
      if (mix) {
        handleClipUpdated(await updateClip(mix.id, clipId, { [field]: value }))
      }
    },
    handleMuteToggle: (clipId: string) => handleToggleFlag(clipId, 'is_muted'),
    handleSoloToggle: (clipId: string) => handleToggleFlag(clipId, 'is_solo'),
    handleClipSplit,
    handleClipDeleted,
    handleSelectedClipDelete: async (clipId: string) => {
      if (!mix) {
        return
      }
      await deleteClip(mix.id, clipId)
      handleClipDeleted(clipId)
    },
  }
}
