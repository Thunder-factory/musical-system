const PLACEHOLDER_TOKENS = ['placeholder', 'your_', 'example', 'dummy']

function isConfiguredEnvValue(value: unknown): boolean {
  if (typeof value !== 'string') {
    return false
  }
  const normalized = value.trim().toLowerCase()
  if (!normalized) {
    return false
  }
  return !PLACEHOLDER_TOKENS.some((token) => normalized.includes(token))
}

/** Comprueba si las variables mínimas de Firebase están definidas con valores reales. */
export function isFirebaseConfigured(): boolean {
  return (
    isConfiguredEnvValue(import.meta.env.VITE_FIREBASE_API_KEY) &&
    isConfiguredEnvValue(import.meta.env.VITE_FIREBASE_DATABASE_URL) &&
    isConfiguredEnvValue(import.meta.env.VITE_FIREBASE_PROJECT_ID)
  )
}
