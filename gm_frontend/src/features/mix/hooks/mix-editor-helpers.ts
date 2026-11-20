import { getSongDetail } from '../../songs/api/songs.api'
import { addClip, type MixProject } from '../api/mix.api'

export async function attachSongToProjectIfNeeded(
  project: MixProject,
  addSongId: string | null
): Promise<{ project: MixProject; addedClipId: string | null; songTitle: string | null }> {
  if (!addSongId || project.clips.some((c) => c.song === addSongId)) {
    return { project, addedClipId: null, songTitle: null }
  }
  const detail = await getSongDetail(addSongId)
  const endMs = Math.round((detail.audio_duration ?? 180) * 1000)
  const newClip = await addClip(project.id, {
    song_id: detail.id,
    position: project.clips.length,
    start_time_ms: 0,
    end_time_ms: endMs > 0 ? endMs : 180_000,
  })
  return {
    project: {
      ...project,
      clips: [...project.clips, newClip],
      clip_count: project.clip_count + 1,
    },
    addedClipId: newClip.id,
    songTitle: detail.title,
  }
}
