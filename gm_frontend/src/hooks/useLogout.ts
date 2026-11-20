import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

import client from '../api/client'
import { ENDPOINTS } from '../api/endpoints'
import { getPushDeviceId } from '../services/firebase-messaging'
import { useAuthStore } from '../store/auth.store'

/** Cierra sesión en el backend (invalida el refresh y el dispositivo push) y luego localmente. */
export function useLogout() {
  const navigate = useNavigate()
  const logout = useAuthStore((state) => state.logout)

  return useCallback(async () => {
    const { refreshToken } = useAuthStore.getState()
    try {
      await client.post(ENDPOINTS.auth.logout, {
        refresh: refreshToken,
        device_id: getPushDeviceId(),
      })
    } catch {
      // La sesión local siempre debe cerrarse aunque el endpoint no responda.
    } finally {
      logout()
      navigate('/login', { replace: true })
    }
  }, [logout, navigate])
}
