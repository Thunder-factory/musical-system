
/**
 * Firebase Cloud Messaging - Service Worker
 *
 * Recibe mensajes push cuando la aplicación está
 * en segundo plano.
 *
 * La configuración pública llega desde React
 * mediante los parámetros de registro.
 */

importScripts(
  'https://www.gstatic.com/firebasejs/12.15.0/firebase-app-compat.js'
)

importScripts(
  'https://www.gstatic.com/firebasejs/12.15.0/firebase-messaging-compat.js'
)

const params = new URL(self.location.href).searchParams

firebase.initializeApp({
  apiKey: params.get('apiKey'),
  authDomain: params.get('authDomain'),
  projectId: params.get('projectId'),
  messagingSenderId: params.get('messagingSenderId'),
  appId: params.get('appId'),
})

const messaging = firebase.messaging()

// Los mensajes con notification normalmente son mostrados
// automáticamente por Firebase en segundo plano.
// Evitamos duplicar esas notificaciones.
messaging.onBackgroundMessage((payload) => {
  if (payload.notification) {
    return
  }

  const title = payload.data?.title || 'Musical System'

  self.registration.showNotification(title, {
    body: payload.data?.body || 'Tienes una nueva notificación.',
    icon: '/logo.png',
  })
})
