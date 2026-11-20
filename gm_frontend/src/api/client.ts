import axios from 'axios'

import { useAuthStore } from '../store/auth.store'

const BASE_URL = '/api'

/**
 * Instancia centralizada de Axios configurada con la URL base de la API.
 * Todos los módulos de API deben usar este cliente en lugar de axios directamente.
 */
const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Adjunta el token JWT Bearer en cada petición saliente si existe sesión activa.
client.interceptors.request.use((config) => {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

const REFRESH_URL = '/auth/refresh/'
const LOGOUT_URL = '/auth/logout/'

// Promesa de refresco compartida: con ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION
// solo el primer refresh es válido, así que todas las peticiones 401 en paralelo esperan
// la misma renovación en vez de lanzar cada una la suya.
let refreshPromise: Promise<string> | null = null

function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    const { refreshToken, setTokens } = useAuthStore.getState()
    refreshPromise = (async () => {
      if (!refreshToken) {
        throw new Error('Sin refresh token')
      }
      const { data } = await axios.post(`${BASE_URL}${REFRESH_URL}`, { refresh: refreshToken })
      // Django rota también el refresh token y deja inválido el anterior.
      setTokens(data.access, data.refresh ?? refreshToken)
      return data.access as string
    })().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

let loggingOut = false

async function forceLogout() {
  if (loggingOut) {
    return
  }
  loggingOut = true
  const { accessToken, refreshToken } = useAuthStore.getState()
  try {
    await axios.post(
      `${BASE_URL}${LOGOUT_URL}`,
      {
        refresh: refreshToken,
        device_id: window.localStorage.getItem('musicai.push-device-id') ?? '',
      },
      accessToken ? { headers: { Authorization: `Bearer ${accessToken}` } } : undefined,
    )
  } catch {
    // La sesión puede haber expirado completamente; la limpieza local continúa.
  } finally {
    useAuthStore.getState().logout()
    window.location.href = '/login'
  }
}

// Refresca el token automáticamente ante un 401 y reintenta la petición original una sola vez.
// Si el refresco falla, cierra la sesión (una sola vez) y redirige al login.
client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const isRefreshCall = original?.url?.includes(REFRESH_URL)
    // Sin refresh token no hay sesión que renovar (p. ej. credenciales incorrectas en el login).
    const hasSession = Boolean(useAuthStore.getState().refreshToken)
    if (error.response?.status === 401 && original && !original._retry && !isRefreshCall && hasSession) {
      original._retry = true
      try {
        const access = await refreshAccessToken()
        original.headers.Authorization = `Bearer ${access}`
        return client(original)
      } catch {
        void forceLogout()
      }
    }
    return Promise.reject(error)
  }
)

export default client
