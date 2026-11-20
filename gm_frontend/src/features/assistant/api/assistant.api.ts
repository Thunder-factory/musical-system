import { isAxiosError } from 'axios'

import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'
import type { AssistantChatRequest, AssistantChatResponse } from '../types/assistant.types'

/** Envía el historial al asistente y devuelve su respuesta con acciones. No cobra créditos. */
export async function sendAssistantChat(
  payload: AssistantChatRequest
): Promise<AssistantChatResponse> {
  const { data } = await client.post<AssistantChatResponse>(ENDPOINTS.assistant.chat, payload)
  return { reply: data.reply ?? '', actions: Array.isArray(data.actions) ? data.actions : [] }
}

/** Traduce un error HTTP del asistente a un mensaje para mostrar en el chat. */
export function getAssistantErrorMessage(error: unknown): string {
  const status = isAxiosError(error) ? error.response?.status : undefined
  if (status === 429) {
    return 'Hiciste muchas preguntas seguidas, espera un rato.'
  }
  if (status === 503) {
    return 'El asistente no está disponible por ahora.'
  }
  return 'No pude responder, intenta de nuevo.'
}

/** Indica si vale la pena ofrecer el botón de reintentar. */
export function isRetryableAssistantError(error: unknown): boolean {
  const status = isAxiosError(error) ? error.response?.status : undefined
  return status !== 429 && status !== 503 && status !== 400 && status !== 401
}
