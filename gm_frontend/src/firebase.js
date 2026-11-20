import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { getDatabase } from 'firebase/database'
import { isFirebaseConfigured } from './lib/env'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

function initFirebaseSafe() {
  if (!isFirebaseConfigured()) {
    return null
  }
  try {
    return initializeApp(firebaseConfig)
  } catch (error) {
    console.error('Error al inicializar Firebase:', error)
    return null
  }
}

export const firebaseApp = initFirebaseSafe()

let authInstance = null
let dbInstance = null

export function getFirebaseAuth() {
  if (!firebaseApp) {
    return null
  }
  if (!authInstance) {
    authInstance = getAuth(firebaseApp)
  }
  return authInstance
}

export function getFirebaseDb() {
  if (!firebaseApp) {
    return null
  }
  if (!dbInstance) {
    dbInstance = getDatabase(firebaseApp)
  }
  return dbInstance
}

export const firebaseAuth = getFirebaseAuth()
export const db = getFirebaseDb()

export default firebaseApp
