import type { ReactNode } from 'react'

interface Props {
  number: number
  title: string
  hint?: string
  done?: boolean
  children: ReactNode
}

/** Tarjeta de un paso numerado del formulario de Cambiar caras. */
export default function FaceSwapStep({ number, title, hint, done = false, children }: Props) {
  return (
    <section
      className="flex flex-col gap-4 rounded-lg bg-card p-5"
      aria-labelledby={`faceswap-step-${number}`}
    >
      <header className="flex items-start gap-3">
        <span
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold"
          style={
            done
              ? { background: 'var(--color-primary)', color: 'var(--color-on-primary)' }
              : { background: 'var(--bg-card-hover)', color: 'var(--text-subdued)' }
          }
          aria-hidden="true"
        >
          {number}
        </span>
        <div className="min-w-0">
          <h2 id={`faceswap-step-${number}`} className="text-base font-bold text-white">
            {title}
          </h2>
          {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
        </div>
      </header>
      {children}
    </section>
  )
}
