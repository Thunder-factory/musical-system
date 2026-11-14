import {
  getMessaging,
  getToken,
  isSupported,
  onMessage,
  type MessagePayload,
} from 'firebase/messaging'

// @ts-expect-error — firebase.js es JS puro; Vite resuelve el módulo correctamente
import firebaseApp from '../firebase.js'
import client from '../api/client'

const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY

function getServiceWorkerUrl(): string {
  const params = new URLSearchParams({
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    messagingSenderId:
      import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
  })

  return `/firebase-messaging-sw.js?${params.toString()}`
}

/**
 * Solicita permiso, registra el service worker,
 * obtiene el token FCM y lo guarda en Django.
 *
 * Debe ejecutarse desde una interacción del usuario.
 */
export async function enableWebPush(): Promise<void> {
  if (!('serviceWorker' in navigator)) {
    throw new Error(
      'El navegador no soporta Service Workers.'
    )
  }

  if (!('Notification' in window)) {
    throw new Error(
      'El navegador no soporta notificaciones.'
    )
  }

  if (!(await isSupported())) {
    throw new Error(
      'Firebase Messaging no está disponible.'
    )
  }

  if (!vapidKey) {
    throw new Error(
      'Falta VITE_FIREBASE_VAPID_KEY.'
    )
  }

  const permission = await Notification.requestPermission()

  if (permission !== 'granted') {
    throw new Error(
      'No se concedió permiso para notificaciones.'
    )
  }

  const registration = await navigator.serviceWorker.register(
    getServiceWorkerUrl(),
    {
      scope: '/',
    }
  )

  const messaging = getMessaging(firebaseApp)

  const token = await getToken(messaging, {
    vapidKey,
    serviceWorkerRegistration: registration,
  })

  if (!token) {
    throw new Error(
      'Firebase no devolvió un token FCM.'
    )
  }

  await client.post('/auth/fcm-token/', {
    fcm_token: token,
  })
}

/**
 * Escucha los mensajes recibidos mientras
 * Musical System está abierto y en primer plano.
 */
export async function listenForegroundNotifications(
  callback: (payload: MessagePayload) => void
): Promise<() => void> {
  if (!(await isSupported())) {
    return () => {}
  }

  const messaging = getMessaging(firebaseApp)

  return onMessage(messaging, callback)
}
