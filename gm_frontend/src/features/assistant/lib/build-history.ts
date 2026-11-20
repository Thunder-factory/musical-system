import type { AssistantMessagePayload, ChatMessage } from '../types/assistant.types'

export const MAX_HISTORY = 12
export const MAX_CONTENT = 1000

/**
 * Convierte el chat en memoria al historial que acepta el backend:
 * sin errores locales, roles alternados (si hay dos seguidos del mismo rol
 * se queda el más reciente), máximo 12 mensajes y empezando por "user".
 */
export function buildHistory(messages: ChatMessage[]): AssistantMessagePayload[] {
  const alternated: AssistantMessagePayload[] = []
  for (const message of messages) {
    if (message.kind !== 'normal' || !message.content.trim()) {
      continue
    }
    const item = { role: message.role, content: message.content.slice(0, MAX_CONTENT) }
    const last = alternated[alternated.length - 1]
    if (last && last.role === item.role) {
      alternated[alternated.length - 1] = item
    } else {
      alternated.push(item)
    }
  }
  const recent = alternated.slice(-MAX_HISTORY)
  while (recent.length > 0 && recent[0].role !== 'user') {
    recent.shift()
  }
  return recent
}
