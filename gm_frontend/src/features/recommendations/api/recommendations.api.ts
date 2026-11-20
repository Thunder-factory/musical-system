import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'
import type { LibrarySong } from '../../songs/api/songs.api'

export interface SuggestedTag {
  id: number
  name: string
}

export async function getForYou(): Promise<LibrarySong[]> {
  const { data } = await client.get<LibrarySong[]>(ENDPOINTS.recommendations.forYou)
  return data
}

export async function getSuggestedTags(): Promise<SuggestedTag[]> {
  const { data } = await client.get<SuggestedTag[]>(ENDPOINTS.recommendations.suggestedTags)
  return data
}
