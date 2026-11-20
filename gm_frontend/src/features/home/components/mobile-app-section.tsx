import { Download, QrCode, ShieldCheck, Smartphone, Users, Bell } from 'lucide-react'

// Descarga directa del APK de la última versión publicada (no abre la página del repositorio).
const APP_DOWNLOAD_URL =
  'https://github.com/mopy1/musicai-mobile/releases/latest/download/app-release.apk'

const BENEFITS = [
  {
    icon: ShieldCheck,
    title: 'Acceso seguro',
    description: 'Ingresa con tus credenciales y mantén tu sesión protegida.',
  },
  {
    icon: Users,
    title: 'Tu música contigo',
    description: 'Consulta tus canciones y proyectos desde cualquier dispositivo.',
  },
  {
    icon: Bell,
    title: 'Siempre al día',
    description: 'Recibe avisos importantes y mantén el control de tu cuenta.',
  },
]

export default function MobileAppSection() {
  return (
    <section
      id="app-movil"
      className="border-t border-border bg-surface px-5 py-20 sm:px-10 lg:px-16"
    >
      <div className="mx-auto grid max-w-[1200px] items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
        <div>
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-xs font-bold uppercase tracking-[0.14em] text-primary">
            <Smartphone size={15} aria-hidden="true" />
            Aplicación móvil
          </div>

          <h2 className="max-w-2xl text-3xl font-extrabold tracking-tight text-white sm:text-5xl">
            MusicAI también en tu móvil
          </h2>

          <p className="mt-5 max-w-2xl text-sm leading-relaxed text-muted sm:text-base">
            Descarga la app móvil y lleva tus canciones, proyectos y herramientas creativas contigo.
          </p>

          <div className="mt-9 grid gap-4 sm:grid-cols-3">
            {BENEFITS.map((benefit) => {
              const Icon = benefit.icon
              return (
                <article
                  key={benefit.title}
                  className="rounded-2xl border border-border bg-card p-4"
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary">
                    <Icon size={18} aria-hidden="true" />
                  </div>
                  <h3 className="text-sm font-bold text-white">{benefit.title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-muted">{benefit.description}</p>
                </article>
              )
            })}
          </div>

          <a
            href={APP_DOWNLOAD_URL}
            download="MusicAI.apk"
            rel="noopener noreferrer"
            className="mt-9 inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-black shadow-[var(--shadow)] transition-colors hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            Descargar la app
            <Download size={16} aria-hidden="true" />
          </a>
        </div>

        <div className="flex justify-center lg:justify-end">
          <div className="relative w-full max-w-[380px]">
            <div className="absolute -left-5 -top-5 h-20 w-20 rotate-12 rounded-3xl bg-primary-soft" />
            <div className="absolute -bottom-5 -right-5 h-24 w-24 -rotate-12 rounded-3xl bg-primary-subtle" />

            <div className="relative rounded-[28px] border border-border bg-card p-6 text-center shadow-[var(--shadow)]">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-black">
                <QrCode size={28} aria-hidden="true" />
              </div>

              <h3 className="mt-5 text-xl font-extrabold text-white">Escanea y descarga</h3>
              <p className="mx-auto mt-2 max-w-xs text-sm leading-relaxed text-muted">
                Usa la cámara de tu teléfono y la app se descarga directamente.
              </p>

              <div className="mx-auto mt-6 flex max-w-[230px] items-center justify-center rounded-3xl border border-border bg-white p-4 shadow-inner">
                <img
                  src="/qr-app.png"
                  alt="Código QR para descargar la aplicación móvil de MusicAI"
                  className="h-44 w-44 object-contain"
                />
              </div>

              <div className="mt-5 rounded-xl border border-border bg-surface p-3 text-left">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted">
                  Disponible
                </p>
                <p className="mt-1 text-sm font-bold text-white">Descarga directa para Android</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
