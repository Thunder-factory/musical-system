import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'
import { getCommunityFeed } from '../../community/api/community.api'
import { getLibrary } from '../../songs/api/songs.api'
import type {
  KaraokeCatalogSong,
  KaraokeGenerateResult,
  KaraokePlayData,
  LyricTimestamp,
  MyKaraokeItem,
} from '../../../types'

export async function getKaraokeCatalog(
  source: 'library' | 'community'
): Promise<KaraokeCatalogSong[]> {
  if (source === 'library') {
    const songs = await getLibrary('karaoke')
    return songs.map((s) => ({
      id: s.id,
      title: s.title,
      thumbnail_url: s.thumbnail_url,
      source: 'library' as const,
      tags: s.tags?.map((t) => t.name) ?? [],
    }))
  }

  const { results } = await getCommunityFeed()
  return results.map((s) => ({
    id: s.id,
    title: s.title,
    thumbnail_url: undefined,
    source: 'community' as const,
    user_name: s.user_name,
    tags: s.tags?.map((t) => t.name) ?? [],
  }))
}

export async function generateKaraoke(songId: string): Promise<KaraokeGenerateResult> {
  const { data } = await client.post<KaraokeGenerateResult>(ENDPOINTS.karaoke.generate(songId))
  return data
}

export async function pollKaraokeStatus(
  karaokeId: string
): Promise<Pick<KaraokeGenerateResult, 'status' | 'processing_stage'> & { error_message?: string }> {
  const { data } = await client.get<{
    status: KaraokeGenerateResult['status']
    processing_stage: KaraokeGenerateResult['processing_stage']
    error_message?: string
  }>(ENDPOINTS.karaoke.status(karaokeId))
  return data
}

interface PlayApiResponse {
  play_url?: string
  audio_url?: string
  instrumental_url?: string
  lyrics?: string
  lyrics_timestamps?: LyricTimestamp[]
  song_title?: string
  title?: string
  song?: { id?: string; title?: string }
  song_thumbnail?: string
  thumbnail_url?: string
}

export async function getKaraokePlayData(karaokeId: string): Promise<KaraokePlayData> {
  const { data } = await client.get<PlayApiResponse>(ENDPOINTS.karaoke.play(karaokeId))
  return {
    play_url: data.play_url ?? data.audio_url ?? data.instrumental_url ?? '',
    lyrics: data.lyrics ?? '',
    lyrics_timestamps: data.lyrics_timestamps ?? [],
    song_title: data.song_title ?? data.title ?? data.song?.title ?? '',
    song_thumbnail: data.song_thumbnail ?? data.thumbnail_url,
  }
}

export async function getMyKaraokes(): Promise<MyKaraokeItem[]> {
  const { data } = await client.get<MyKaraokeItem[]>(ENDPOINTS.karaoke.myLibrary)
  return data
}

export interface CreateKaraokeRoomResult {
  room_code: string
  credit_balance: number
}

export interface JoinKaraokeRoomResult {
  room_code: string
  joined: boolean
  is_host: boolean
}

export async function createKaraokeRoom(karaokeId: string): Promise<CreateKaraokeRoomResult> {
  const { data } = await client.post<CreateKaraokeRoomResult>(ENDPOINTS.karaoke.createRoom, {
    karaoke_id: karaokeId,
  })
  return data
}

export async function joinKaraokeRoom(roomCode: string): Promise<JoinKaraokeRoomResult> {
  const { data } = await client.post<JoinKaraokeRoomResult>(ENDPOINTS.karaoke.joinRoom(roomCode))
  return data
}
