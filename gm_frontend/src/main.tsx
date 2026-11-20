import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import { ConfirmDialogHost, Toaster } from './components/ui'
import { isFirebaseConfigured } from './lib/env'
import { router } from './router/index'
import { logoutFirebase } from './services/firebase-auth'
import { useAuthStore } from './store/auth.store'

// Cerrar Firebase cuando termine o cambie la sesión autenticada de Django.
useAuthStore.subscribe((state, previousState) => {
  if (!isFirebaseConfigured()) {
    return
  }
  const loggedOut = previousState.accessToken !== null && state.accessToken === null
  const userChanged =
    previousState.user?.id !== undefined && previousState.user?.id !== state.user?.id

  if (loggedOut || userChanged) {
    void logoutFirebase().catch((error: unknown) => {
      console.error('Error al cerrar Firebase:', error)
    })
  }
})

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
      <ConfirmDialogHost />
    </QueryClientProvider>
  </StrictMode>
)
