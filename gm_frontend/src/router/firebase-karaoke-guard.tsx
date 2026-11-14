import { useEffect, useState, type ReactNode } from 'react'

import { authenticateFirebase } from '../services/firebase-auth'
import { useAuthStore } from '../store/auth.store'

// @ts-expect-error — firebase.js es un módulo JavaScript.
import { firebaseAuth } from '../firebase.js'

interface Props {
  children: ReactNode
}

export default function FirebaseKaraokeGuard({ children }: Props) {
  const userId = useAuthStore((state) => state.user?.id)
  const accessToken = useAuthStore((state) => state.accessToken)

  const [readyUserId, setReadyUserId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!userId || !accessToken) {
      return
    }

    let cancelled = false

    authenticateFirebase(userId)
      .then(() => {
        if (!cancelled) {
          setReadyUserId(userId)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setReadyUserId(null)
          setError(
            err instanceof Error ? err.message : 'No se pudo conectar con Firebase.',
          )
        }
      })

    return () => {
      cancelled = true
    }
  }, [userId, accessToken, attempt])

  if (!userId || !accessToken) {
    return <p>Debes iniciar sesión.</p>
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <p>No se pudo autenticar la sala de karaoke.</p>
        <p>{error}</p>
        <button
          type="button"
          onClick={() => {
            setError(null)
            setReadyUserId(null)
            setAttempt((value) => value + 1)
          }}
        >
          Reintentar
        </button>
      </div>
    )
  }

  if (readyUserId !== userId || firebaseAuth.currentUser?.uid !== userId) {
    return <p className="p-6">Conectando con Firebase...</p>
  }

  return <>{children}</>
}
