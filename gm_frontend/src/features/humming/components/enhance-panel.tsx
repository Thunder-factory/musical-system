import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'

import { Button } from '../../../components/ui'
import {
  enhanceHumming,
  getHummingErrorMessage,
  getHummingStyles,
  isNoCreditsError,
  type HummingFidelity,
  type HummingJob,
} from '../api/humming.api'
import { CUSTOM_HUMMING_STYLE } from '../lib/humming-constants'
import EnhancementRow from './enhance-enhancement-row'
import EnhanceStylePicker from './enhance-style-picker'

interface EnhancePanelProps {
  job: HummingJob
  versionLabel: (number: number) => string
  onRequested: () => void
  refresh: () => Promise<HummingJob | null>
}

export default function EnhancePanel({
  job,
  versionLabel,
  onRequested,
  refresh,
}: EnhancePanelProps) {
  const { data: catalog } = useQuery({
    queryKey: ['humming-styles'],
    queryFn: getHummingStyles,
    staleTime: Infinity,
  })
  const [style, setStyle] = useState('')
  const [customStyle, setCustomStyle] = useState('')
  const [fidelity, setFidelity] = useState<HummingFidelity>('media')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<{ message: string; noCredits: boolean } | null>(null)

  const groups = useMemo(() => {
    const map = new Map<string, NonNullable<typeof catalog>['styles']>()
    for (const item of catalog?.styles ?? []) {
      map.set(item.group, [...(map.get(item.group) ?? []), item])
    }
    return [...map.entries()]
  }, [catalog])

  if (!catalog) {
    return null
  }

  const cost = catalog.credit_cost
  const canSubmit =
    catalog.available &&
    !sending &&
    Boolean(style) &&
    (style !== CUSTOM_HUMMING_STYLE || customStyle.trim().length > 0)

  async function handleSubmit() {
    if (!canSubmit) {
      return
    }
    setSending(true)
    setError(null)
    try {
      await enhanceHumming(job.id, {
        style,
        fidelity,
        ...(style === CUSTOM_HUMMING_STYLE ? { custom_style: customStyle.trim() } : {}),
      })
      setStyle('')
      setCustomStyle('')
      onRequested()
    } catch (err) {
      setError({
        noCredits: isNoCreditsError(err),
        message: isNoCreditsError(err)
          ? 'No tienes créditos suficientes.'
          : getHummingErrorMessage(err, 'No se pudo pedir la mejora. Intenta de nuevo.'),
      })
    } finally {
      setSending(false)
    }
  }

  return (
    <section
      className="flex flex-col gap-4 rounded-xl border border-primary-border bg-primary-soft p-5"
      aria-labelledby="humming-enhance-title"
    >
      <div>
        <h3
          id="humming-enhance-title"
          className="inline-flex items-center gap-2 font-semibold text-white"
        >
          <Sparkles size={18} className="text-primary" aria-hidden="true" />
          Mejorar con IA
        </h3>
        <p className="mt-1 text-sm text-muted">
          Elige cualquier estilo y la IA rehace tu canción en ese estilo, conservando tu melodía.
          Partimos solo de la versión que más se le parece.
        </p>
      </div>

      {!catalog.available ? (
        <p className="text-sm text-muted">La mejora con IA no está disponible por ahora.</p>
      ) : (
        <>
          <EnhanceStylePicker
            groups={groups}
            fidelities={catalog.fidelities}
            style={style}
            customStyle={customStyle}
            fidelity={fidelity}
            onStyleChange={setStyle}
            onCustomStyleChange={setCustomStyle}
            onFidelityChange={setFidelity}
          />

          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={() => void handleSubmit()}
              disabled={!canSubmit}
              loading={sending}
              costCredits={cost}
              leftIcon={<Sparkles size={16} aria-hidden="true" />}
            >
              Mejorar con IA
            </Button>
            <span className="text-xs text-muted">
              Recibirás varias versiones para elegir. Tarda de 30 s a 2 minutos.
            </span>
          </div>

          {error && (
            <p className="text-sm text-error" role="alert">
              {error.message}{' '}
              {error.noCredits && (
                <Link to="/payments" className="font-semibold text-primary underline">
                  Recargar créditos
                </Link>
              )}
            </p>
          )}
        </>
      )}

      {job.enhancements.length > 0 && (
        <ul className="flex flex-col gap-2" aria-label="Versiones mejoradas con IA">
          {job.enhancements.map((item) => (
            <EnhancementRow
              key={item.id}
              item={item}
              job={job}
              refresh={refresh}
              versionLabel={versionLabel}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
