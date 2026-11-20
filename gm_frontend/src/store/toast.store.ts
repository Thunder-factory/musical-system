import { create } from 'zustand'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface ToastItem {
  id: string
  type: ToastType
  title: string
  description?: string
}

export type NewToast = Omit<ToastItem, 'id'>

interface ToastState {
  toasts: ToastItem[]
  pushToast: (toast: NewToast) => string
  dismissToast: (id: string) => void
}

const AUTO_DISMISS_MS = 4500
const dismissTimers = new Map<string, number>()

function createToastId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  pushToast: (item) => {
    const id = createToastId()
    set((state) => ({ toasts: [...state.toasts, { ...item, id }] }))

    if (typeof window !== 'undefined') {
      const timer = window.setTimeout(() => {
        get().dismissToast(id)
      }, AUTO_DISMISS_MS)
      dismissTimers.set(id, timer)
    }

    return id
  },
  dismissToast: (id) => {
    const timer = dismissTimers.get(id)
    if (timer !== undefined) {
      window.clearTimeout(timer)
      dismissTimers.delete(id)
    }
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
  },
}))

export const toast = {
  success: (title: string, description?: string) =>
    useToastStore.getState().pushToast({ type: 'success', title, description }),
  error: (title: string, description?: string) =>
    useToastStore.getState().pushToast({ type: 'error', title, description }),
  info: (title: string, description?: string) =>
    useToastStore.getState().pushToast({ type: 'info', title, description }),
  warning: (title: string, description?: string) =>
    useToastStore.getState().pushToast({ type: 'warning', title, description }),
}
