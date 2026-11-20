import { isAxiosError } from 'axios'

import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'
import type { AuthUser } from '../../../store/auth.store'

export interface LoginResponse {
  access: string
  refresh: string
}

export interface RegisterPayload {
  full_name: string
  email: string
  password: string
}

const FIELD_LABELS: Record<string, string> = {
  email: 'Correo electrónico',
  password: 'Contraseña',
  full_name: 'Nombre completo',
}

export async function loginRequest(email: string, password: string): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>(ENDPOINTS.auth.login, { email, password })
  return data
}

export async function registerRequest(payload: RegisterPayload): Promise<void> {
  await client.post(ENDPOINTS.auth.register, payload)
}

export async function getMeRequest(): Promise<AuthUser> {
  const { data } = await client.get<AuthUser>(ENDPOINTS.auth.me)
  return data
}

export function formatAuthError(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) {
    return fallback
  }
  if (!error.response) {
    return 'No se pudo conectar con el servidor. Intenta de nuevo.'
  }

  const data = error.response.data
  if (typeof data === 'string' && data.trim()) {
    return data
  }
  if (!data || typeof data !== 'object') {
    return fallback
  }

  const record = data as Record<string, unknown>
  if (typeof record.detail === 'string' && record.detail.trim()) {
    return record.detail
  }
  if (typeof record.message === 'string' && record.message.trim()) {
    return record.message
  }

  const nonField = record.non_field_errors
  if (Array.isArray(nonField) && typeof nonField[0] === 'string') {
    return nonField[0]
  }

  const messages: string[] = []
  for (const [key, value] of Object.entries(record)) {
    const label = FIELD_LABELS[key]
    if (Array.isArray(value)) {
      const first = value.find((item) => typeof item === 'string')
      if (typeof first === 'string') {
        messages.push(label ? `${label}: ${first}` : first)
      }
    } else if (typeof value === 'string' && value.trim()) {
      messages.push(label ? `${label}: ${value}` : value)
    }
  }

  return messages[0] ?? fallback
}
