import { create } from 'zustand'

import {
  getAssistantErrorMessage,
  isRetryableAssistantError,
  sendAssistantChat,
} from '../api/assistant.api'
import { buildHistory, MAX_CONTENT } from '../lib/build-history'
import type { ChatMessage } from '../types/assistant.types'

interface AssistantState {
  open: boolean
  typing: boolean
  /** Historial solo en memoria (se pierde al recargar). */
  messages: ChatMessage[]
  setOpen: (open: boolean) => void
  /** Envía una pregunta del usuario con la ruta actual como contexto. */
  send: (text: string, page: string) => Promise<void>
  /** Reintenta la última pregunta tras un error. */
  retry: (page: string) => Promise<void>
  reset: () => void
}

let counter = 0
const newId = () => `m-${Date.now()}-${++counter}`

export const useAssistantStore = create<AssistantState>()((set, get) => {
  async function request(page: string) {
    const history = buildHistory(get().messages)
    if (history.length === 0 || history[history.length - 1].role !== 'user') {
      return
    }
    set({ typing: true })
    try {
      const data = await sendAssistantChat({ messages: history, page: page.slice(0, 100) })
      const reply: ChatMessage = {
        id: newId(),
        role: 'assistant',
        content: data.reply || 'No tengo una respuesta para eso, prueba a preguntarlo de otra forma.',
        actions: data.actions.slice(0, 3),
        kind: 'normal',
      }
      set((state) => ({ messages: [...state.messages, reply] }))
    } catch (error) {
      const failure: ChatMessage = {
        id: newId(),
        role: 'assistant',
        content: getAssistantErrorMessage(error),
        kind: 'error',
        retryable: isRetryableAssistantError(error),
      }
      set((state) => ({ messages: [...state.messages, failure] }))
    } finally {
      set({ typing: false })
    }
  }

  return {
    open: false,
    typing: false,
    messages: [],
    setOpen: (open) => set({ open }),
    send: async (text, page) => {
      const content = text.trim().slice(0, MAX_CONTENT)
      if (!content || get().typing) {
        return
      }
      const message: ChatMessage = { id: newId(), role: 'user', content, kind: 'normal' }
      set((state) => ({ messages: [...state.messages, message] }))
      await request(page)
    },
    retry: async (page) => {
      if (get().typing) {
        return
      }
      set((state) => ({ messages: state.messages.filter((m) => m.kind !== 'error') }))
      await request(page)
    },
    reset: () => set({ open: false, typing: false, messages: [] }),
  }
})
