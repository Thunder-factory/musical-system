import {
  inMemoryPersistence,
  setPersistence,
  signInWithCustomToken,
  signOut,
} from 'firebase/auth'

import client from '../api/client'
import { ENDPOINTS } from '../api/endpoints'

// @ts-expect-error — firebase.js es un módulo JavaScript.
import { firebaseAuth } from '../firebase.js'

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

  if (firebaseAuth.currentUser?.uid === expectedUserId) {
    return
  }

  await setPersistence(firebaseAuth, inMemoryPersistence)

  const { data } = await client.post<FirebaseTokenResponse>(ENDPOINTS.auth.firebaseToken)
  const credential = await signInWithCustomToken(firebaseAuth, data.firebase_token)

  if (credential.user.uid !== expectedUserId) {
    await signOut(firebaseAuth)
    throw new Error('La identidad de Firebase no coincide con Django.')
  }
}

/** Cierra exclusivamente la sesión Firebase. */
export async function logoutFirebase(): Promise<void> {
  await signOut(firebaseAuth)
}
