import {
  inMemoryPersistence,
  setPersistence,
  signInWithCustomToken,
  signOut,
} from 'firebase/auth'

import client from '../api/client'
import { ENDPOINTS } from '../api/endpoints'
import { isFirebaseConfigured } from '../lib/env'

// @ts-expect-error — firebase.js es un módulo JavaScript.
import { getFirebaseAuth } from '../firebase.js'

interface FirebaseTokenResponse {
  firebase_token: string
}

/**
 * Autentica en Firebase al usuario que ya inició sesión mediante JWT en Django.
 */
export async function authenticateFirebase(expectedUserId: string): Promise<void> {
  if (!expectedUserId) {
    throw new Error('No existe un usuario autenticado.')
  }

  const firebaseAuth = isFirebaseConfigured() ? getFirebaseAuth() : null
  if (!firebaseAuth) {
    throw new Error('Firebase no está configurado en este entorno.')
  }

  if (firebaseAuth.currentUser?.uid === expectedUserId) {
    return
  }

  await setPersistence(firebaseAuth, inMemoryPersistence)

  const { data } = await client.post<FirebaseTokenResponse>(ENDPOINTS.auth.firebaseToken)
  const credential = await signInWithCustomToken(firebaseAuth, data.firebase_token)

  if (credential.user.uid !== expectedUserId) {
    await signOut(firebaseAuth)
    throw new Error('La identidad de Firebase no coincide con tu cuenta.')
  }
}

/** Cierra exclusivamente la sesión Firebase si está inicializada. */
export async function logoutFirebase(): Promise<void> {
  const firebaseAuth = isFirebaseConfigured() ? getFirebaseAuth() : null
  if (!firebaseAuth) {
    return
  }
  await signOut(firebaseAuth)
}
