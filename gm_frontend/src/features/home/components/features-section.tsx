import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  AudioLines,
  AudioWaveform,
  Languages,
  Mic2,
  Music2,
  ScanFace,
  SlidersHorizontal,
} from 'lucide-react'

import { Button } from '../../../components/ui'

interface FeaturesSectionProps {
  isAuthenticated: boolean
}

const STUDIO_TOOLS = [
  {
    to: '/humming',
    icon: AudioLines,
    title: 'Tararear',
    desc: 'Graba una melodía con tu voz y transfórmala en versiones producidas con IA.',
  },
  {
    to: '/stems',
    icon: AudioWaveform,
    title: 'Separar pistas',
    desc: 'Aísla voz e instrumental de cualquier canción de tu biblioteca o archivo.',
  },
  {
    to: '/karaoke',
    icon: Mic2,
    title: 'Karaoke',
    desc: 'Genera pistas con letra sincronizada y canta en salas en vivo con amigos.',
  },
  {
    to: '/traducciones',
    icon: Languages,
    title: 'Traducciones',
    desc: 'Dobla videos musicales a otros idiomas conservando la voz y entonación.',
  },
  {
    to: '/faceswap',
    icon: ScanFace,
    title: 'Cambiar caras',
    desc: 'Integra tu rostro en clips musicales en minutos con plantillas o tu propio video.',
  },
  {
    to: '/mix',
    icon: SlidersHorizontal,
    title: 'Mix DJ',
    desc: 'Combina, recorta y organiza tus pistas en una línea de tiempo multipista.',
  },
]

export function FeaturesSection({ isAuthenticated }: FeaturesSectionProps) {
  const navigate = useNavigate()

  return (
    <section id="features" className="bg-night px-5 py-20 sm:px-10 lg:px-16">
      <div className="mx-auto max-w-[1200px]">
        <div className="mb-10 max-w-2xl">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-4xl">
            Un estudio completo para crear música y video
          </h2>
          <p className="mt-2.5 text-sm leading-relaxed text-muted sm:text-base">
            Todas las herramientas de MusicAI conectadas en un mismo espacio de trabajo.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="flex flex-col justify-between gap-6 rounded-2xl border border-primary-border bg-surface p-6 lg:col-span-5">
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                  <Music2 size={20} aria-hidden="true" />
                </div>
                <h3 className="text-xl font-bold text-white">Crear canción</h3>
              </div>
              <p className="text-sm leading-relaxed text-muted">
                Genera temas completos a partir de una descripción libre, tu letra exacta o una
                historia guiada. Ajusta duración, voz, idioma y estilo en un solo panel.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button onClick={() => navigate(isAuthenticated ? '/create' : '/register')}>
                <span className="inline-flex items-center gap-2">
                  <span>{isAuthenticated ? 'Abrir creador' : 'Empezar a crear'}</span>
                  <ArrowRight size={15} aria-hidden="true" />
                </span>
              </Button>
              {isAuthenticated && (
                <Button variant="secondary" onClick={() => navigate('/inicio')}>
                  Ir a mi estudio
                </Button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:col-span-7">
            {STUDIO_TOOLS.map((tool) => {
              const Icon = tool.icon
              return (
                <Link
                  key={tool.to}
                  to={isAuthenticated ? tool.to : '/register'}
                  className="group flex flex-col gap-2 rounded-2xl border border-border bg-card p-5 transition-colors hover:border-primary"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-soft text-primary">
                      <Icon size={18} aria-hidden="true" />
                    </span>
                    <ArrowRight
                      size={15}
                      aria-hidden="true"
                      className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
                    />
                  </div>
                  <h3 className="mt-1 text-base font-bold text-white">{tool.title}</h3>
                  <p className="text-xs leading-relaxed text-muted">{tool.desc}</p>
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}

export default FeaturesSection
