import { useAuthStore } from '../../../store/auth.store'
import type { AssistantAction } from '../types/assistant.types'
import AssistantActions from './assistant-actions'

const QUICK_ACTIONS: AssistantAction[] = [
  { label: 'Crear canción', route: '/create' },
  { label: 'Cambiar caras', route: '/faceswap' },
  { label: 'Karaoke', route: '/karaoke' },
]

/** Saludo local (no consulta la API) con nombre, créditos y accesos rápidos. */
export default function AssistantWelcome() {
  const user = useAuthStore((s) => s.user)
  const firstName = user?.full_name?.trim().split(/\s+/)[0] || 'artista'
  const credits = user?.credit_balance ?? 0

  return (
    <li className="flex justify-start">
      <div className="max-w-[88%] rounded-2xl rounded-bl-md border border-primary-border bg-primary-soft px-3.5 py-2.5 text-sm leading-relaxed text-white/90">
        <p>
          ¡Hola, <strong className="font-semibold text-white">{firstName}</strong>! Tienes{' '}
          <strong className="font-semibold text-primary">
            {credits} {credits === 1 ? 'crédito' : 'créditos'}
          </strong>
          . ¿Qué te gustaría hacer?
        </p>
        <AssistantActions actions={QUICK_ACTIONS} />
      </div>
    </li>
  )
}
