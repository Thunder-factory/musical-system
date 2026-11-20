import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { LoaderCircle, MicOff, RefreshCw } from 'lucide-react'

import { isFirebaseConfigured } from '../lib/env'
import { authenticateFirebase } from '../services/firebase-auth'
import { useAuthStore } from '../store/auth.store'

// @ts-expect-error — firebase.js es un módulo JavaScript.
import { getFirebaseAuth } from '../firebase.js'

interface Props {
  children: ReactNode
}

export default function FirebaseKaraokeGuard({ children }: Props) {
  const userId = useAuthStore((state) => state.user?.id)
  const accessToken = useAuthStore((state) => state.accessToken)
  const firebaseConfigured = isFirebaseConfigured()

  const [readyUserId, setReadyUserId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!firebaseConfigured || !userId || !accessToken) {
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
          setError(err instanceof Error ? err.message : 'No se pudo conectar con Firebase.')
        }
      })

    return () => {
      cancelled = true
    }
  }, [firebaseConfigured, userId, accessToken, attempt])

  if (!firebaseConfigured) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <div className="max-w-md rounded-xl border border-border bg-card p-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-error-soft text-error">
            <MicOff size={22} aria-hidden="true" />
          </div>
          <h2 className="text-lg font-bold text-white">Salas en vivo no disponibles</h2>
          <p className="mt-2 text-sm text-muted">
            Las salas compartidas de karaoke requieren configurar Firebase en este entorno.
          </p>
          <Link
            to="/karaoke"
            className="mt-5 inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-primary-hover"
          >
            ← Volver a Karaoke
          </Link>
        </div>
      </div>
    )
  }

  if (!userId || !accessToken) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <p className="text-sm text-muted">Debes iniciar sesión para unirte a una sala.</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <div className="max-w-md rounded-xl border border-error-border bg-card p-6 text-center">
          <h2 className="text-lg font-bold text-white">No se pudo autenticar la sala de karaoke</h2>
          <p className="mt-2 text-sm text-error">{error}</p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => {
                setError(null)
                setReadyUserId(null)
                setAttempt((value) => value + 1)
              }}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-primary-hover"
            >
              <RefreshCw size={15} aria-hidden="true" />
              Reintentar
            </button>
            <Link
              to="/karaoke"
              className="inline-flex items-center justify-center rounded-lg border border-border-strong bg-card-hover px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-border-strong"
            >
              ← Volver a Karaoke
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const firebaseAuth = getFirebaseAuth()
  if (readyUserId !== userId || firebaseAuth?.currentUser?.uid !== userId) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center gap-2.5 p-6 text-sm text-muted">
        <LoaderCircle size={18} className="animate-spin text-primary" aria-hidden="true" />
        <span>Conectando con la sala de karaoke...</span>
      </div>
    )
  }

  return <>{children}</>
}
