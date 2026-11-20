import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import AdminLayout from '../components/layout/admin-layout'
import AppLayout from '../components/layout/app-layout'
import AuthLayout from '../components/layout/auth-layout'
import AdminRoute from './admin-route'
import FirebaseKaraokeGuard from './firebase-karaoke-guard'
import PrivateRoute from './private-route'

const HomePage = lazy(() => import('../features/home/pages/home-page'))
const InicioPage = lazy(() => import('../features/home/pages/inicio-page'))

const LoginPage = lazy(() => import('../features/auth/pages/login-page'))
const RegisterPage = lazy(() => import('../features/auth/pages/register-page'))

const DashboardPage = lazy(() => import('../features/admin/pages/dashboard-page'))
const PlanesPage = lazy(() => import('../features/admin/pages/planes-page'))
const RolesPage = lazy(() => import('../features/admin/pages/roles-page'))
const AdminProfilePage = lazy(() => import('../features/admin/pages/admin-profile-page'))
const UsersAdminPage = lazy(() => import('../features/admin/pages/users-admin-page'))
const ReportsAdminPage = lazy(() => import('../features/admin/pages/reports-admin-page'))
const FaceSwapTemplatesPage = lazy(
  () => import('../features/admin/pages/faceswap-templates-page')
)

const ProfilePage = lazy(() => import('../features/billing/pages/profile-page'))
const PaymentsPage = lazy(() => import('../features/billing/pages/payments-page'))
const CommunityPage = lazy(() => import('../features/community/pages/community-page'))

const LibraryPage = lazy(() => import('../features/songs/pages/library-page'))
const CreatePage = lazy(() => import('../features/songs/pages/create-page'))
const StemsPage = lazy(() => import('../features/stems/pages/stems-page'))
const HummingPage = lazy(() => import('../features/humming/pages/humming-page'))
const TranslationsPage = lazy(() => import('../features/translations/pages/translations-page'))
const FaceSwapPage = lazy(() => import('../features/faceswap/pages/faceswap-page'))
const ForYouPage = lazy(() => import('../features/recommendations/pages/for-you-page'))
const PlaylistsPage = lazy(() => import('../features/playlists/pages/playlists-page'))
const PlaylistDetailPage = lazy(() => import('../features/playlists/pages/playlist-detail-page'))
const PublicPlaylistPage = lazy(() => import('../features/playlists/pages/public-playlist-page'))
const MixPage = lazy(() => import('../features/mix/pages/mix-page'))
const MixEditorPage = lazy(() => import('../features/mix/pages/mix-editor-page'))
const KaraokePage = lazy(() => import('../features/karaoke/pages/karaoke-page'))
const KaraokeGeneratePage = lazy(
  () => import('../features/karaoke/pages/karaoke-generate-page')
)
const KaraokePlayerPage = lazy(() => import('../features/karaoke/pages/karaoke-player-page'))
const KaraokeRoomPage = lazy(() => import('../features/karaoke/pages/karaoke-room-page'))

function PageLoader() {
  return (
    <div className="flex h-full items-center justify-center p-8 text-sm text-muted">
      Cargando...
    </div>
  )
}

function withSuspense(element: React.ReactElement) {
  return <Suspense fallback={<PageLoader />}>{element}</Suspense>
}

export const router = createBrowserRouter([
  { path: '/', element: withSuspense(<HomePage />) },
  { path: '/playlists/public/:token', element: withSuspense(<PublicPlaylistPage />) },

  {
    element: <AuthLayout />,
    children: [
      { path: '/login', element: withSuspense(<LoginPage />) },
      { path: '/register', element: withSuspense(<RegisterPage />) },
    ],
  },

  {
    element: <PrivateRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/inicio', element: withSuspense(<InicioPage />) },
          { path: '/library', element: withSuspense(<LibraryPage />) },
          { path: '/create', element: withSuspense(<CreatePage />) },
          { path: '/stems', element: withSuspense(<StemsPage />) },
          { path: '/humming', element: withSuspense(<HummingPage />) },
          { path: '/traducciones', element: withSuspense(<TranslationsPage />) },
          { path: '/faceswap', element: withSuspense(<FaceSwapPage />) },
          { path: '/community', element: withSuspense(<CommunityPage />) },
          { path: '/recommendations', element: withSuspense(<ForYouPage />) },
          { path: '/playlists', element: withSuspense(<PlaylistsPage />) },
          { path: '/playlists/:id', element: withSuspense(<PlaylistDetailPage />) },
          { path: '/profile', element: withSuspense(<ProfilePage />) },
          { path: '/payments', element: withSuspense(<PaymentsPage />) },
          { path: '/mix', element: withSuspense(<MixPage />) },
          { path: '/mix/:id', element: withSuspense(<MixEditorPage />) },
          { path: '/karaoke', element: withSuspense(<KaraokePage />) },
          { path: '/karaoke/generate/:songId', element: withSuspense(<KaraokeGeneratePage />) },
          { path: '/karaoke/play/:karaokeId', element: withSuspense(<KaraokePlayerPage />) },
          {
            path: '/karaoke/room/:roomCode',
            element: (
              <FirebaseKaraokeGuard>
                {withSuspense(<KaraokeRoomPage />)}
              </FirebaseKaraokeGuard>
            ),
          },
        ],
      },

      {
        element: <AdminRoute />,
        children: [
          {
            element: <AdminLayout />,
            children: [
              { path: '/admin', element: withSuspense(<DashboardPage />) },
              { path: '/admin/roles', element: withSuspense(<RolesPage />) },
              { path: '/admin/planes', element: withSuspense(<PlanesPage />) },
              { path: '/admin/plantillas', element: withSuspense(<FaceSwapTemplatesPage />) },
              { path: '/admin/usuarios', element: withSuspense(<UsersAdminPage />) },
              { path: '/admin/reportes', element: withSuspense(<ReportsAdminPage />) },
              { path: '/admin/profile', element: withSuspense(<AdminProfilePage />) },
            ],
          },
        ],
      },
    ],
  },

  { path: '*', element: <Navigate to="/" replace /> },
])
