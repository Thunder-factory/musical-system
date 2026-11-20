import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'

export interface LyricsSegment {
  start: number
  end: number
  text: string
}

export interface GenerateSongPayload {
  title?: string
  description?: string
  prompt?: string
  lyrics?: string
  described_lyrics?: string
  audio_duration?: number
  vocal_type?: 'male' | 'female' | 'auto'
  language?: 'es' | 'en'
  instrumental?: boolean
  guidance_scale?: number
  infer_step?: number
}

export interface GenerateSongResponse {
  job_id: string
  song_id: string
  status: 'queued'
}

export type JobStatus = 'queued' | 'processing' | 'ready' | 'no_credits' | 'error'

export interface JobStatusResponse {
  status: JobStatus
  song_id: string
}

export interface SongJobSummary {
  id: string
  status: JobStatus
  song_id: string | null
  title: string
  song_title: string
  error_message: string | null
  created_at: string
}

export interface SignedUrlResponse {
  url: string
}

export interface SongTag {
  id: number | string
  name: string
  slug?: string
}

export interface LibrarySong {
  id: string
  title: string
  description: string
  prompt: string
  genre?: string
  mood?: string
  audio_duration?: number
  created_at: string
  thumbnail_url?: string
  thumbnail_s3_key?: string
  play_url?: string
  tags?: SongTag[]
  is_public?: boolean
  source_type?: 'generated' | 'uploaded'
  status?: string
  like_count?: number
  is_liked?: boolean
}

export interface UploadSongResponse extends LibrarySong {
  source_type: 'uploaded'
}

export interface SongDetail extends LibrarySong {
  lyrics?: string
  described_lyrics?: string
  lyrics_source?: string
  instrumental?: boolean
  guidance_scale?: number
  infer_step?: number
  seed?: number
  status?: string
  is_public?: boolean
  updated_at?: string
  lyrics_timestamps?: LyricsSegment[]
}

export async function generateSong(payload: GenerateSongPayload): Promise<GenerateSongResponse> {
  const { data } = await client.post<GenerateSongResponse>(ENDPOINTS.songs.generate, payload)
  return data
}

export async function uploadSong(
  file: File,
  title?: string,
  onProgress?: (progress: number) => void
): Promise<UploadSongResponse> {
  const form = new FormData()
  form.append('file', file)
  if (title?.trim()) {
    form.append('title', title.trim())
  }
  const { data } = await client.post<UploadSongResponse>(ENDPOINTS.songs.upload, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (event.total) {
        onProgress?.(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return data
}

export async function getSongJobs(activeOnly = false): Promise<SongJobSummary[]> {
  const { data } = await client.get<SongJobSummary[]>(ENDPOINTS.songs.jobs, {
    params: activeOnly ? { active: '1' } : undefined,
  })
  return data
}

export async function getSongJob(jobId: string): Promise<JobStatusResponse> {
  const { data } = await client.get<JobStatusResponse>(ENDPOINTS.songs.job(jobId))
  return data
}

export async function getSongPlayUrl(songId: string): Promise<string> {
  const { data } = await client.get<SignedUrlResponse>(ENDPOINTS.songs.playUrl(songId))
  return data.url
}

export async function getSongThumbnailUrl(songId: string): Promise<string> {
  const { data } = await client.get<SignedUrlResponse>(ENDPOINTS.songs.thumbnailUrl(songId))
  return data.url
}

export async function getLibrary(context?: 'karaoke'): Promise<LibrarySong[]> {
  const { data } = await client.get<LibrarySong[]>(ENDPOINTS.songs.library, {
    params: context ? { context } : undefined,
  })
  return data
}

export async function getSongDetail(songId: string): Promise<SongDetail> {
  const { data } = await client.get<SongDetail>(ENDPOINTS.songs.detail(songId))
  return data
}

export async function deleteSong(songId: string): Promise<void> {
  await client.delete(ENDPOINTS.songs.delete(songId))
}

export async function toggleSongPublic(songId: string, isPublic: boolean): Promise<void> {
  await client.patch(ENDPOINTS.songs.update(songId), { is_public: isPublic })
}

export async function toggleSongLike(
  songId: string
): Promise<{ liked: boolean; like_count: number }> {
  const { data } = await client.post<{ liked: boolean; like_count: number }>(
    ENDPOINTS.songs.like(songId)
  )
  return data
}
