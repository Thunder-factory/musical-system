import { Headphones, PenLine, SlidersHorizontal } from 'lucide-react'

const STEPS = [
  {
    icon: PenLine,
    title: 'Describe tu idea',
    desc: 'Escribe el estilo, emoción o historia que imaginas, o graba un tarareo rápido.',
  },
  {
    icon: SlidersHorizontal,
    title: 'Personaliza el resultado',
    desc: 'Elige género, ambiente, tempo, tipo de voz e idioma según tu proyecto.',
  },
  {
    icon: Headphones,
    title: 'Produce y comparte',
    desc: 'Escucha tu canción, separa pistas, cántala en karaoke o mézclala en el estudio.',
  },
]

export function HowItWorksSection() {
  return (
    <section className="border-y border-border bg-surface px-5 py-16 sm:px-10 lg:px-16">
      <div className="mx-auto max-w-[1200px]">
        <div className="mb-10 max-w-xl">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            De una idea a una canción completa
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Flujo directo pensado para pasar de la inspiración a la mezcla final sin complicaciones.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
          {STEPS.map((step) => {
            const Icon = step.icon
            return (
              <div key={step.title} className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                  <Icon size={20} aria-hidden="true" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">{step.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{step.desc}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

export default HowItWorksSection
