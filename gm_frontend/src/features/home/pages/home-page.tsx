import { Link, useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'

import { Button } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import FeaturesSection from '../components/features-section'
import HeroSection from '../components/hero-section'
import HowItWorksSection from '../components/how-it-works-section'
import MobileAppSection from '../components/mobile-app-section'

export default function HomePage() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => Boolean(s.accessToken && s.user))

  function scrollToFeatures() {
    document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-night text-white">
      <nav className="sticky top-0 z-40 flex h-[70px] items-center justify-between border-b border-border bg-surface/95 px-5 backdrop-blur-md sm:px-10 lg:px-16">
        <Link to="/" className="flex items-center gap-2.5">
          <img src="/logo.png" alt="MusicAI" className="h-9 w-9 object-contain" />
          <span className="text-xl font-bold tracking-tight text-primary">MusicAI</span>
          <Sparkles size={14} className="text-primary" aria-hidden="true" />
        </Link>

        <div className="flex items-center gap-2.5">
          {isAuthenticated ? (
            <Button onClick={() => navigate('/inicio')}>Ir a mi estudio</Button>
          ) : (
            <>
              <Button
                variant="secondary"
                onClick={() => navigate('/login')}
                className="hidden sm:inline-flex"
              >
                Iniciar sesión
              </Button>
              <Button onClick={() => navigate('/register')}>Cuenta gratuita</Button>
            </>
          )}
        </div>
      </nav>

      <main>
        <HeroSection isAuthenticated={isAuthenticated} onExplore={scrollToFeatures} />
        <HowItWorksSection />
        <FeaturesSection isAuthenticated={isAuthenticated} />
        <MobileAppSection />

        <section className="border-t border-border bg-surface px-5 py-20 text-center sm:px-10">
          <div className="mx-auto max-w-xl space-y-5">
            <h2 className="text-2xl font-extrabold tracking-tight text-white sm:text-4xl">
              Tu próxima canción empieza con una idea
            </h2>
            <p className="text-sm leading-relaxed text-muted sm:text-base">
              Crea gratis y descubre todo lo que puedes producir con MusicAI.
            </p>
            <Button size="lg" onClick={() => navigate(isAuthenticated ? '/inicio' : '/register')}>
              {isAuthenticated ? 'Ir a mi estudio' : 'Empezar gratis'}
            </Button>
          </div>
        </section>
      </main>

      <footer className="flex flex-col items-start justify-between gap-4 border-t border-border bg-night px-5 py-6 sm:flex-row sm:items-center sm:px-10 lg:px-16">
        <div className="flex items-center gap-2.5">
          <img src="/logo.png" alt="MusicAI" className="h-7 w-7 object-contain" />
          <span className="text-sm font-bold text-primary">MusicAI</span>
        </div>

        <div className="flex items-center gap-5 text-xs text-muted">
          {isAuthenticated ? (
            <Link to="/inicio" className="hover:text-white">
              Mi estudio
            </Link>
          ) : (
            <>
              <Link to="/login" className="hover:text-white">
                Iniciar sesión
              </Link>
              <Link to="/register" className="hover:text-white">
                Crear cuenta
              </Link>
            </>
          )}
        </div>

        <span className="text-xs text-muted">© 2026 MusicAI</span>
      </footer>
    </div>
  )
}
