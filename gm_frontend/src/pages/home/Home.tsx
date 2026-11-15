import { useNavigate } from 'react-router-dom'
import { Headphones, PenLine, Play, SlidersHorizontal, Sparkles } from 'lucide-react'
import responsiveStyles from './Home.module.css'

export default function Home() {
  const navigate = useNavigate()

  return (
    <div className={responsiveStyles.page} style={s.pageWrapper}>
      <Navbar navigate={navigate} />
      <main style={s.main}>
        {/* HERO */}
        <section className={responsiveStyles.hero} style={s.hero}>
          <div className={responsiveStyles.heroContainer} style={s.heroContainer}>
            <div className={responsiveStyles.heroContent} style={s.heroContent}>
              <p style={s.heroTag}>MÚSICA GENERADA CON IA</p>
              <h1 className={responsiveStyles.heroTitle} style={s.heroTitle}>
                Convierte una idea en una canción
              </h1>
              <p className={responsiveStyles.heroDesc} style={s.heroDesc}>
                Describe el estilo, la emoción o la historia. MusicAI crea la música y la letra por
                ti.
              </p>
              <div className={responsiveStyles.heroButtons} style={s.heroButtons}>
                <button style={s.btnCreate} onClick={() => navigate('/register')}>
                  <img src="/logo-2.png" alt="" aria-hidden="true" style={s.heroButtonLogo} />
                  Crear mi canción
                </button>
                <button
                  style={s.btnExplore}
                  onClick={() =>
                    document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })
                  }
                >
                  Explorar la plataforma
                </button>
              </div>
              <div style={s.heroBenefits}>
                <span style={s.heroBenefit}>Genera canciones</span>
                <span style={s.heroBenefit}>Separa voces</span>
                <span style={s.heroBenefit}>Mezcla tus tracks</span>
              </div>
            </div>
            <div className={responsiveStyles.heroImage} style={s.heroImage}>
              <img
                src="/fondo_home.png"
                alt="MusicAI"
                style={{
                  width: '100%',
                  maxWidth: 820,
                  borderRadius: 20,
                  boxShadow: 'var(--shadow)',
                }}
              />
              <div className={responsiveStyles.heroPreviewCard} style={s.heroPreviewCard}>
                <div style={s.heroPreviewTopline}>
                  <span style={s.heroPreviewStatus}>Tu canción está lista</span>
                  <span style={s.heroPreviewTime}>0:42</span>
                </div>
                <div style={s.heroPreviewTrack}>
                  <div style={s.heroPreviewPlay}>
                    <Play size={14} fill="currentColor" aria-hidden="true" />
                  </div>
                  <div style={s.heroPreviewDetails}>
                    <strong style={s.heroPreviewTitle}>Sueño Eléctrico</strong>
                    <span style={s.heroPreviewMeta}>Voz · Instrumental</span>
                  </div>
                </div>
                <div style={s.heroPreviewProgress}>
                  <span style={s.heroPreviewProgressValue} />
                </div>
              </div>
            </div>
          </div>
        </section>

        <HowItWorks />

        {/* FEATURES */}
        <Features />
        <FinalCta navigate={navigate} />
        <Footer navigate={navigate} />
      </main>
    </div>
  )
}

const HOW_IT_WORKS = [
  {
    icon: <PenLine size={22} />,
    number: '01',
    title: 'Describe tu idea',
    desc: 'Escribe el estilo, emoción o historia que imaginas.',
  },
  {
    icon: <SlidersHorizontal size={22} />,
    number: '02',
    title: 'Personaliza el resultado',
    desc: 'Elige género, mood, tempo, voz e idioma.',
  },
  {
    icon: <Headphones size={22} />,
    number: '03',
    title: 'Crea y disfruta',
    desc: 'Genera tu canción, escúchala y sigue trabajando en ella.',
  },
]

function HowItWorks() {
  return (
    <section className={responsiveStyles.howItWorks} style={s.howItWorks}>
      <div className={responsiveStyles.howItWorksContainer} style={s.howItWorksContainer}>
        <div style={s.howItWorksHeader}>
          <p style={s.featuresTag}>ASÍ DE FÁCIL</p>
          <h2 style={s.howItWorksTitle}>De una idea a una canción</h2>
        </div>
        <div style={s.stepsGrid}>
          {HOW_IT_WORKS.map((step) => (
            <div key={step.number} style={s.step}>
              <div style={s.stepIcon}>{step.icon}</div>
              <span style={s.stepNumber}>{step.number}</span>
              <h3 style={s.stepTitle}>{step.title}</h3>
              <p style={s.stepDesc}>{step.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function Navbar({ navigate }: { navigate: (path: string) => void }) {
  return (
    <nav className={responsiveStyles.navbar} style={s.navbar}>
      <div style={s.brand}>
        <img
          src="/logo.png"
          alt="MusicAI"
          style={{ width: 48, height: 48, objectFit: 'contain' }}
        />
        <span style={s.brandName}>MusicAI</span>
        <Sparkles
          size={14}
          strokeWidth={2.5}
          aria-label="Inteligencia artificial"
          style={s.brandAiIcon}
        />
      </div>
      <div className={responsiveStyles.navActions} style={s.navActions}>
        <button style={s.btnLogin} onClick={() => navigate('/login')}>
          Iniciar sesión
        </button>
        <button style={s.btnRegister} onClick={() => navigate('/register')}>
          Cuenta gratuita
        </button>
      </div>
    </nav>
  )
}

const FEATURES = [
  {
    icon: '🎵',
    title: 'Crea música',
    desc: 'Describe una idea y conviértela en una canción con IA.',
  },
  {
    icon: '🎤',
    title: 'Separa voces',
    desc: 'Obtén voces e instrumentales de cualquier canción.',
  },
  {
    icon: '🎛️',
    title: 'Mezcla tus tracks',
    desc: 'Combina tus canciones y crea sets únicos.',
  },
  {
    icon: '🌐',
    title: 'Comparte con la comunidad',
    desc: 'Descubre creaciones y conecta con otros artistas.',
  },
]

function Features() {
  return (
    <section id="features" className={responsiveStyles.features} style={s.features}>
      <div className={responsiveStyles.featuresContainer} style={s.featuresContainer}>
        <div style={s.featuresHeader}>
          <p style={s.featuresTag}>TODO LO QUE NECESITAS</p>
          <h2 style={s.featuresTitle}>Todo para crear música</h2>
        </div>
        <div style={s.featuresGrid}>
          {FEATURES.map(({ icon, title, desc }) => (
            <div key={title} style={s.featureCard}>
              <div style={s.featureIconWrap}>
                <span style={{ fontSize: '2.5rem' }}>{icon}</span>
              </div>
              <h3 style={s.featureCardTitle}>{title}</h3>
              <p style={s.featureCardDesc}>{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function FinalCta({ navigate }: { navigate: (path: string) => void }) {
  return (
    <section className={responsiveStyles.finalCta} style={s.finalCta}>
      <div style={s.finalCtaContent}>
        <p style={s.featuresTag}>EMPIEZA A CREAR</p>
        <h2 style={s.finalCtaTitle}>Tu próxima canción empieza con una idea</h2>
        <p style={s.finalCtaDesc}>Crea gratis y descubre lo que puedes hacer con MusicAI.</p>
        <button style={s.btnCreate} onClick={() => navigate('/register')}>
          Empezar gratis
        </button>
      </div>
    </section>
  )
}

function Footer({ navigate }: { navigate: (path: string) => void }) {
  return (
    <footer className={responsiveStyles.footer} style={s.footer}>
      <div style={s.footerBrand}>
        <img src="/logo.png" alt="MusicAI" style={s.footerLogo} />
        <span style={s.brandName}>MusicAI</span>
      </div>
      <div style={s.footerLinks}>
        <button type="button" onClick={() => navigate('/login')}>
          Iniciar sesión
        </button>
        <button type="button" onClick={() => navigate('/register')}>
          Crear cuenta
        </button>
      </div>
      <span style={s.footerCopyright}>© 2026 MusicAI</span>
    </footer>
  )
}

const s: Record<string, React.CSSProperties> = {
  pageWrapper: {
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    background: 'var(--bg-base)',
    color: 'var(--text-base)',
    overflowX: 'hidden',
    overflowY: 'auto',
    minHeight: '100vh',
    height: '100vh',
  },
  navbar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100%',
    padding: '0 80px',
    height: 70,
    background: 'var(--bg-surface)',
    borderBottom: '1px solid var(--border)',
    boxSizing: 'border-box',
    zIndex: 1000,
  },
  brand: { display: 'flex', alignItems: 'center', gap: 12 },
  brandName: {
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    fontSize: '1.4rem',
    fontWeight: 700,
    color: 'var(--color-primary)',
    letterSpacing: '-0.5px',
  },
  brandAiIcon: { color: 'var(--color-primary)', marginLeft: -6 },
  navActions: { display: 'flex', alignItems: 'center', gap: 16 },
  btnLogin: {
    background: 'var(--bg-card-hover)',
    border: '1px solid var(--border-strong)',
    fontSize: '0.95rem',
    fontWeight: 500,
    color: 'var(--text-base)',
    cursor: 'pointer',
    padding: '8px 16px',
    borderRadius: 10,
  },
  btnRegister: {
    background: 'var(--color-primary)',
    color: 'var(--text-base)',
    border: 'none',
    padding: '0 20px',
    height: 40,
    lineHeight: '36px',
    borderRadius: 10,
    fontSize: '0.95rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  main: { paddingTop: 70 },
  hero: {
    minHeight: 'calc(100vh - 70px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 9%',
    background:
      'radial-gradient(ellipse 42% 68% at 66% 50%, color-mix(in srgb, var(--color-primary) 28%, transparent) 0%, transparent 100%)',
  },
  heroContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 70,
    width: '100%',
    maxWidth: 1400,
    flexWrap: 'wrap',
  },
  heroContent: { flex: 1, maxWidth: 600 },
  heroTag: {
    display: 'inline-flex',
    alignItems: 'center',
    color: 'var(--color-info)',
    background: 'var(--color-primary-soft)',
    border: '1px solid var(--color-primary-border)',
    borderRadius: 999,
    padding: '6px 10px',
    fontSize: '0.9rem',
    fontWeight: 700,
    letterSpacing: '1.5px',
    textTransform: 'uppercase',
    marginBottom: 12,
  },
  heroTitle: {
    maxWidth: 560,
    fontSize: '3.4rem',
    fontWeight: 700,
    lineHeight: 1.1,
    color: 'var(--text-base)',
    marginBottom: 24,
  },
  heroDesc: {
    maxWidth: 520,
    fontSize: '1.1rem',
    color: 'var(--text-subdued)',
    lineHeight: 1.8,
    marginBottom: 0,
  },
  heroButtons: { display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 28 },
  btnCreate: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    background: 'var(--color-primary)',
    color: 'var(--text-base)',
    border: 'none',
    padding: '0 32px',
    height: 50,
    lineHeight: '40px',
    borderRadius: 10,
    fontSize: '1rem',
    fontWeight: 700,
    cursor: 'pointer',
  },
  heroButtonLogo: { width: 32, height: 32, objectFit: 'contain' },
  btnExplore: {
    background: 'transparent',
    color: 'var(--text-base)',
    border: '1px solid var(--border-strong)',
    padding: '0 24px',
    height: 50,
    borderRadius: 10,
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  heroBenefits: { display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 28 },
  heroBenefit: {
    color: 'var(--text-subdued)',
    fontSize: '0.85rem',
    paddingRight: 10,
    borderRight: '1px solid var(--border)',
  },
  howItWorks: {
    background: 'var(--bg-surface)',
    borderTop: '1px solid var(--border)',
    borderBottom: '1px solid var(--border)',
    padding: '72px 0',
  },
  howItWorksContainer: { width: '100%', maxWidth: 1400, margin: '0 auto', padding: '0 10%' },
  howItWorksHeader: { textAlign: 'center', marginBottom: 42 },
  howItWorksTitle: { fontSize: '2rem', color: 'var(--text-base)', fontWeight: 800, margin: 0 },
  stepsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 32,
  },
  step: { position: 'relative', paddingLeft: 56, minHeight: 92 },
  stepIcon: {
    position: 'absolute',
    top: 0,
    left: 0,
    display: 'grid',
    placeItems: 'center',
    width: 40,
    height: 40,
    borderRadius: 10,
    background: 'var(--color-primary-soft)',
    color: 'var(--color-primary)',
  },
  stepNumber: {
    display: 'block',
    marginBottom: 8,
    color: 'var(--text-subdued)',
    fontSize: '0.7rem',
    fontWeight: 800,
    letterSpacing: 1,
  },
  stepTitle: { margin: '0 0 6px', color: 'var(--text-base)', fontSize: '1rem', fontWeight: 700 },
  stepDesc: { margin: 0, color: 'var(--text-subdued)', fontSize: '0.9rem', lineHeight: 1.5 },
  heroImage: {
    flex: 1,
    display: 'flex',
    justifyContent: 'center',
    position: 'relative',
  },
  heroPreviewCard: {
    position: 'absolute',
    right: '4%',
    bottom: 18,
    width: 250,
    padding: '14px 16px',
    border: '1px solid var(--color-primary-border)',
    borderRadius: 14,
    background: 'color-mix(in srgb, var(--bg-card) 94%, transparent)',
    boxShadow: 'var(--shadow)',
    backdropFilter: 'blur(12px)',
  },
  heroPreviewTopline: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    marginBottom: 12,
  },
  heroPreviewStatus: {
    color: 'var(--color-primary)',
    fontSize: '0.72rem',
    fontWeight: 700,
  },
  heroPreviewTime: { color: 'var(--text-subdued)', fontSize: '0.7rem' },
  heroPreviewTrack: { display: 'flex', alignItems: 'center', gap: 10 },
  heroPreviewPlay: {
    width: 30,
    height: 30,
    flexShrink: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '50%',
    background: 'var(--color-primary)',
    color: 'var(--bg-base)',
  },
  heroPreviewDetails: { minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 },
  heroPreviewTitle: {
    color: 'var(--text-base)',
    fontSize: '0.8rem',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  heroPreviewMeta: { color: 'var(--text-subdued)', fontSize: '0.7rem' },
  heroPreviewProgress: {
    height: 3,
    marginTop: 13,
    overflow: 'hidden',
    borderRadius: 999,
    background: 'var(--bg-card-hover)',
  },
  heroPreviewProgressValue: {
    display: 'block',
    width: '38%',
    height: '100%',
    borderRadius: 999,
    background: 'var(--color-primary)',
  },
  heroImgPlaceholder: {
    width: '100%',
    maxWidth: 520,
    height: 360,
    background: 'var(--bg-card)',
    border: '2px dashed var(--border)',
    borderRadius: 20,
  },
  features: {
    background: 'var(--bg-surface)',
    padding: '100px 0',
    display: 'flex',
    justifyContent: 'center',
  },
  featuresContainer: { width: '100%', maxWidth: 1400, padding: '0 10%' },
  featuresHeader: { textAlign: 'center', marginBottom: 60 },
  featuresTag: {
    color: 'var(--color-info)',
    fontSize: '0.85rem',
    fontWeight: 700,
    letterSpacing: 2,
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  featuresTitle: { fontSize: '2.5rem', color: 'var(--text-base)', fontWeight: 800 },
  featuresGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
    gap: 32,
  },
  featureCard: {
    background: 'var(--bg-card)',
    padding: '40px',
    borderRadius: 20,
    border: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
  },
  featureIconWrap: {
    width: 80,
    height: 80,
    background: 'var(--color-primary-soft)',
    borderRadius: 15,
    border: '2px solid var(--color-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 25,
  },
  featureCardTitle: {
    fontSize: '1.4rem',
    color: 'var(--text-base)',
    marginBottom: 15,
    fontWeight: 700,
  },
  featureCardDesc: {
    color: 'var(--text-subdued)',
    lineHeight: 1.6,
    margin: 0,
    fontSize: '0.95rem',
  },
  finalCta: {
    display: 'flex',
    justifyContent: 'center',
    background: 'var(--bg-base)',
    padding: '96px 10%',
    textAlign: 'center',
  },
  finalCtaContent: { maxWidth: 620 },
  finalCtaTitle: {
    margin: '0 0 14px',
    color: 'var(--text-base)',
    fontSize: '2.2rem',
    fontWeight: 800,
  },
  finalCtaDesc: { margin: '0 0 26px', color: 'var(--text-subdued)', fontSize: '1rem' },
  footer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 24,
    background: 'var(--bg-surface)',
    borderTop: '1px solid var(--border)',
    padding: '24px 10%',
  },
  footerBrand: { display: 'flex', alignItems: 'center', gap: 10 },
  footerLogo: { width: 32, height: 32, objectFit: 'contain' },
  footerLinks: { display: 'flex', gap: 20 },
  footerCopyright: { color: 'var(--text-subdued)', fontSize: '0.8rem' },
}
