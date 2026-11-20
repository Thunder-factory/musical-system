import type { ReactNode } from 'react'
import {
  AudioLines,
  AudioWaveform,
  BarChart3,
  Clapperboard,
  Coins,
  CreditCard,
  Home,
  Languages,
  LayoutDashboard,
  Library,
  ListMusic,
  Mic2,
  Music2,
  ScanFace,
  Shield,
  SlidersHorizontal,
  Sparkles,
  UserRound,
  Users,
  UsersRound,
} from 'lucide-react'

export interface AppNavItem {
  to: string
  label: string
  icon: ReactNode
}

export interface AppNavGroup {
  title: string
  items: AppNavItem[]
}

export const APP_NAV_GROUPS: AppNavGroup[] = [
  {
    title: 'Inicio',
    items: [{ to: '/inicio', label: 'Inicio', icon: <Home size={18} aria-hidden="true" /> }],
  },
  {
    title: 'Crear',
    items: [
      { to: '/create', label: 'Crear canción', icon: <Music2 size={18} aria-hidden="true" /> },
      { to: '/humming', label: 'Tararear', icon: <AudioLines size={18} aria-hidden="true" /> },
      { to: '/faceswap', label: 'Cambiar caras', icon: <ScanFace size={18} aria-hidden="true" /> },
    ],
  },
  {
    title: 'Estudio',
    items: [
      { to: '/stems', label: 'Separar pistas', icon: <AudioWaveform size={18} aria-hidden="true" /> },
      { to: '/traducciones', label: 'Traducciones', icon: <Languages size={18} aria-hidden="true" /> },
      { to: '/karaoke', label: 'Karaoke', icon: <Mic2 size={18} aria-hidden="true" /> },
      { to: '/mix', label: 'Mix DJ', icon: <SlidersHorizontal size={18} aria-hidden="true" /> },
    ],
  },
  {
    title: 'Mi música',
    items: [
      { to: '/library', label: 'Biblioteca', icon: <Library size={18} aria-hidden="true" /> },
      { to: '/playlists', label: 'Playlists', icon: <ListMusic size={18} aria-hidden="true" /> },
      { to: '/recommendations', label: 'Para ti', icon: <Sparkles size={18} aria-hidden="true" /> },
      { to: '/community', label: 'Comunidad', icon: <UsersRound size={18} aria-hidden="true" /> },
    ],
  },
]

const EXTRA_ROUTES: AppNavItem[] = [
  { to: '/profile', label: 'Mi perfil', icon: <UserRound size={18} aria-hidden="true" /> },
  { to: '/payments', label: 'Pagos y plan', icon: <CreditCard size={18} aria-hidden="true" /> },
]

const ALL_APP_ROUTES: AppNavItem[] = [...APP_NAV_GROUPS.flatMap((g) => g.items), ...EXTRA_ROUTES]

export function getAppRouteMeta(pathname: string): AppNavItem {
  const lower = pathname.toLowerCase()
  const matched = ALL_APP_ROUTES.find(
    ({ to }) => lower === to.toLowerCase() || lower.startsWith(`${to.toLowerCase()}/`)
  )
  return matched ?? { to: '/inicio', label: 'MusicAI', icon: <Music2 size={18} aria-hidden="true" /> }
}

export const ADMIN_NAV: AppNavItem[] = [
  { to: '/admin', label: 'Dashboard', icon: <LayoutDashboard size={17} aria-hidden="true" /> },
  { to: '/admin/usuarios', label: 'Usuarios', icon: <Users size={17} aria-hidden="true" /> },
  { to: '/admin/roles', label: 'Roles', icon: <Shield size={17} aria-hidden="true" /> },
  { to: '/admin/planes', label: 'Planes', icon: <Coins size={17} aria-hidden="true" /> },
  { to: '/admin/plantillas', label: 'Plantillas de video', icon: <Clapperboard size={17} aria-hidden="true" /> },
  { to: '/admin/reportes', label: 'Reportes', icon: <BarChart3 size={17} aria-hidden="true" /> },
  { to: '/admin/profile', label: 'Mi perfil', icon: <UserRound size={17} aria-hidden="true" /> },
]
