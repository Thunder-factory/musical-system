import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'
import type { LibrarySong } from '../../songs/api/songs.api'

export interface TrendingSongItem {
  id: string
  title: string
  user_name: string
  thumbnail_s3_key: string | null
  tags: { id: number; name: string }[]
}

export async function fetchTrendingSongs(): Promise<TrendingSongItem[]> {
  const { data } = await client.get<TrendingSongItem[]>(ENDPOINTS.community.trending)
  return data
}

export async function fetchForYouSongs(): Promise<LibrarySong[]> {
  const { data } = await client.get<LibrarySong[]>(ENDPOINTS.recommendations.forYou)
  return data
}
