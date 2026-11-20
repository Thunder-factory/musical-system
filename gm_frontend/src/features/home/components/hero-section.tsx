import { Play } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../../../components/ui'

interface HeroSectionProps {
  isAuthenticated: boolean
  onExplore: () => void
}

export function HeroSection({ isAuthenticated, onExplore }: HeroSectionProps) {
  const navigate = useNavigate()

  return (
    <section
      className="flex min-h-[calc(100vh-70px)] items-center px-5 py-14 sm:px-10 lg:px-16"
      style={{
        background:
          'radial-gradient(ellipse 46% 68% at 68% 50%, color-mix(in srgb, var(--color-primary) 24%, transparent) 0%, transparent 100%)',
      }}
    >
      <div className="mx-auto grid w-full max-w-[1280px] grid-cols-1 items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
        <div className="flex flex-col items-start gap-6">
          <h1 className="max-w-[540px] text-4xl font-extrabold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-[54px]">
            Convierte una idea en una canción
          </h1>

          <p className="max-w-[500px] text-base leading-relaxed text-muted sm:text-lg">
            Describe el estilo, la emoción o la historia. MusicAI crea la música y la letra por ti
            en segundos.
          </p>

          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <Button
              size="lg"
              onClick={() => navigate(isAuthenticated ? '/inicio' : '/register')}
              leftIcon={
                <img src="/logo-2.png" alt="" aria-hidden="true" className="h-5 w-5 object-contain" />
              }
            >
              {isAuthenticated ? 'Ir a mi estudio' : 'Crear mi canción'}
            </Button>
            <Button variant="secondary" size="lg" onClick={onExplore}>
              Explorar la plataforma
            </Button>
          </div>

          <ul className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-2 text-xs font-medium text-muted">
            <li>Genera canciones</li>
            <li aria-hidden="true" className="text-border-strong">
              •
            </li>
            <li>Separa voces e instrumental</li>
            <li aria-hidden="true" className="text-border-strong">
              •
            </li>
            <li>Mezcla y dobla videos</li>
          </ul>
        </div>

        <div className="relative flex justify-center">
          <img
            src="/fondo_home.png"
            alt="Estudio creativo de MusicAI"
            className="w-full max-w-[720px] rounded-2xl border border-border object-cover shadow-[var(--shadow)]"
          />

          <div className="absolute bottom-4 right-4 w-[240px] rounded-xl border border-primary-border bg-card/95 p-3.5 shadow-[var(--shadow)] backdrop-blur-md sm:bottom-6 sm:right-6">
            <div className="mb-2.5 flex items-center justify-between text-xs">
              <span className="font-semibold text-primary">Tu canción está lista</span>
              <span className="tabular-nums text-muted">0:42</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-black">
                <Play size={14} fill="currentColor" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-bold text-white">Sueño Eléctrico</p>
                <p className="text-[11px] text-muted">Voz · Instrumental</p>
              </div>
            </div>
            <div className="mt-3 h-1 overflow-hidden rounded-full bg-card-hover">
              <span className="block h-full w-2/5 rounded-full bg-primary" />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default HeroSection
