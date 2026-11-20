const key = (userId: string) => `musicai-assistant-seen-${userId}`

/** Lee el flag de "ya vio el asistente"; si el storage falla se asume visto para no molestar. */
export function hasSeenAssistant(userId: string): boolean {
  try {
    return window.localStorage.getItem(key(userId)) === '1'
  } catch {
    return true
  }
}

export function markAssistantSeen(userId: string): void {
  try {
    window.localStorage.setItem(key(userId), '1')
  } catch {
    // Sin storage disponible (modo privado o bloqueado): se ignora.
  }
}
