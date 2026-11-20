import { Link } from 'react-router-dom'
import {
  AudioLines,
  AudioWaveform,
  Languages,
  Music2,
  ScanFace,
  SlidersHorizontal,
} from 'lucide-react'

const QUICK_TOOLS = [
  {
    to: '/create',
    icon: Music2,
    title: 'Crear canción',
    desc: 'Música y letra desde tu idea',
  },
  {
    to: '/humming',
    icon: AudioLines,
    title: 'Tararear',
    desc: 'Convierte tu voz en temas',
  },
  {
    to: '/faceswap',
    icon: ScanFace,
    title: 'Cambiar caras',
    desc: 'Tu rostro en un videoclip',
  },
  {
    to: '/stems',
    icon: AudioWaveform,
    title: 'Separar pistas',
    desc: 'Extrae voz e instrumental',
  },
  {
    to: '/traducciones',
    icon: Languages,
    title: 'Traducciones',
    desc: 'Dobla videos a otro idioma',
  },
  {
    to: '/mix',
    icon: SlidersHorizontal,
    title: 'Mix DJ',
    desc: 'Mezcla y edita tus pistas',
  },
]

export function QuickToolsGrid() {
  return (
    <section aria-label="Accesos rápidos">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {QUICK_TOOLS.map((tool) => {
          const Icon = tool.icon
          return (
            <Link
              key={tool.to}
              to={tool.to}
              className="group flex items-center gap-3.5 rounded-xl border border-border bg-card px-4 py-3.5 transition-colors hover:border-primary"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary transition-colors group-hover:bg-primary group-hover:text-black">
                <Icon size={18} aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-white">{tool.title}</p>
                <p className="truncate text-xs text-muted">{tool.desc}</p>
              </div>
            </Link>
          )
        })}
      </div>
    </section>
  )
}

export default QuickToolsGrid
