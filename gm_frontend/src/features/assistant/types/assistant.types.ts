/** Rol de un mensaje del chat (contrato POST /api/assistant/chat/). */
export type AssistantRole = 'user' | 'assistant'

/** Rutas a las que el asistente puede proponer navegar. */
export type AssistantRoute =
  | '/inicio'
  | '/library'
  | '/create'
  | '/stems'
  | '/humming'
  | '/traducciones'
  | '/faceswap'
  | '/community'
  | '/recommendations'
  | '/playlists'
  | '/profile'
  | '/payments'
  | '/mix'
  | '/karaoke'

/** Botón de acción sugerido por el asistente. */
export interface AssistantAction {
  label: string
  route: AssistantRoute
}

/** Mensaje tal como viaja al backend. */
export interface AssistantMessagePayload {
  role: AssistantRole
  content: string
}

export interface AssistantChatRequest {
  /** 1..12 mensajes, alternados y empezando por "user"; el último debe ser "user". */
  messages: AssistantMessagePayload[]
  /** Ruta actual del front (<= 100 caracteres). */
  page?: string
}

export interface AssistantChatResponse {
  reply: string
  /** 0..3 acciones. */
  actions: AssistantAction[]
}

/** Mensaje en memoria del chat (incluye errores locales que no se envían). */
export interface ChatMessage {
  id: string
  role: AssistantRole
  content: string
  actions?: AssistantAction[]
  /** `error`: mensaje local de fallo, nunca se envía al backend. */
  kind: 'normal' | 'error'
  /** Si el error permite reintentar la última pregunta. */
  retryable?: boolean
}
