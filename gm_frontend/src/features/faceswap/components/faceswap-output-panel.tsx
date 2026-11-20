import { Clapperboard } from 'lucide-react'

import type { FaceSwapStatus } from '../types/faceswap.types'
import FaceSwapProgress from './faceswap-progress'
import FaceSwapResult from './faceswap-result'

interface Props {
  jobId: string | null
  title?: string
  status: FaceSwapStatus | null
  progress: number
  error: string | null
  loadingStatus: boolean
}

const STEPS = ['Sube una foto de tu cara', 'Elige una plantilla o tu clip', 'Genera y descarga']

export default function FaceSwapOutputPanel({ jobId, title, ...state }: Props) {
  return (
    <section
      className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 xl:sticky xl:top-0"
      aria-labelledby="faceswap-output-title"
    >
      <div className="min-w-0">
        <h2 id="faceswap-output-title" className="text-base font-bold text-white">
          Resultado
        </h2>
        {jobId && title && <p className="mt-0.5 truncate text-xs text-muted">{title}</p>}
      </div>

      {!jobId ? (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border-strong px-6 py-9 text-center">
          <Clapperboard size={32} className="text-muted" aria-hidden="true" />
          <p className="text-sm text-muted">Tu video aparecerá aquí.</p>
          <ol className="flex flex-col gap-2 text-left text-sm">
            {STEPS.map((step, i) => (
              <li key={step} className="flex items-center gap-2 text-white">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-card-hover text-[11px] font-bold text-muted">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </div>
      ) : state.status === 'completed' ? (
        <FaceSwapResult jobId={jobId} />
      ) : (
        <FaceSwapProgress {...state} />
      )}
    </section>
  )
}
