import { create } from 'zustand'

import { authService } from '../api/auth-service'
import { useAuthStore } from './auth.store'

export type ActiveJobKind = 'song' | 'humming' | 'stems' | 'translation' | 'faceswap' | 'mix'

export type ActiveJobStatus =
  | 'queued'
  | 'processing'
  | 'ready'
  | 'completed'
  | 'failed'
  | 'error'

export interface ActiveJob {
  id: string
  kind: ActiveJobKind
  label: string
  route: string
  status: ActiveJobStatus
  progressPct?: number
}

interface ActiveJobsState {
  jobs: ActiveJob[]
  upsertJob: (job: ActiveJob) => void
  removeJob: (id: string) => void
}

export const useActiveJobsStore = create<ActiveJobsState>((set) => ({
  jobs: [],
  upsertJob: (job) =>
    set((state) => {
      const index = state.jobs.findIndex((item) => item.id === job.id)
      if (index === -1) {
        return { jobs: [job, ...state.jobs] }
      }
      const next = [...state.jobs]
      next[index] = { ...next[index], ...job }
      return { jobs: next }
    }),
  removeJob: (id) =>
    set((state) => ({
      jobs: state.jobs.filter((item) => item.id !== id),
    })),
}))

/** Sincroniza el perfil y saldo de créditos del usuario tras completar un proceso. */
export async function refreshAuthBalance(): Promise<void> {
  try {
    const profile = await authService.getProfile()
    useAuthStore.getState().setUser(profile)
  } catch (error) {
    console.error('No se pudo actualizar el saldo de créditos:', error)
  }
}
