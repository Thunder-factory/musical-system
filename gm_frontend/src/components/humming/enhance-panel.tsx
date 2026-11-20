import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Check, LoaderCircle, Pause, Play, Sparkles } from 'lucide-react'

import {
  chooseEnhancementVariant,
  enhanceHumming,
  getHummingErrorMessage,
  getHummingStyles,
  isNoCreditsError,
} from '../../api/modules/humming.api'
import type { HummingEnhancement, HummingFidelity, HummingJob } from '../../api/modules/humming.api'
import { useGlobalAudioPlayer } from '../player/use-global-audio-player'
import SimilarityBadge from './similarity-badge'

const CUSTOM = 'custom'

const FIDELITY_LABELS: Record<HummingFidelity, { label: string; hint: string }> = {
  alta: { label: 'Alta', hint: 'Respeta mucho tu melodía; cambia menos el sonido.' },
  media: { label: 'Media', hint: 'Equilibrio entre tu melodía y el estilo elegido.' },
  libre: { label: 'Libre', hint: 'Cambia más el estilo; la melodía puede variar.' },
}

interface Props {
  job: HummingJob
  versionLabel: (number: number) => string
  onRequested: () => void
  refresh: () => Promise<HummingJob | null>
}

const VARIANT_LETTERS = ['A', 'B', 'C']

function EnhancementRow({
  item,
  job,
  refresh,
  versionLabel,
}: {
  item: HummingEnhancement
  job: HummingJob
  refresh: () => Promise<HummingJob | null>
  versionLabel: (number: number) => string
}) {
  const { track, isPlaying, playTrack, pause } = useGlobalAudioPlayer()
  const [choosing, setChoosing] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const busy = item.status === 'queued' || item.status === 'processing'
  const chosen = item.chosen_variant
  const several = item.variants.length > 1

  const trackId = (number: number) => `humming-ai:${item.id}:${number}`
  const label = (number: number) =>
    several || chosen ? `Versión ${VARIANT_LETTERS[number - 1]}` : ''

  async function handlePlay(number: number) {
    if (track?.id === trackId(number) && isPlaying) {
      pause()
      return
    }
    // Renueva las URLs firmadas justo antes de reproducir.
    const fresh = await refresh().catch(() => null)
    const latest = fresh?.enhancements.find((enhancement) => enhancement.id === item.id) ?? item
    const variant = latest.variants.find((v) => v.number === number)
    if (!variant) {
      return
    }
    playTrack({
      id: trackId(number),
      audioUrl: variant.audio_url,
      title: `${job.title || 'Tu tarareo'} · ${item.style_label}`,
      subtitle: `Mejorado con IA${label(number) ? ` · ${label(number)}` : ''}`,
      coverUrl: latest.cover_url,
    })
  }

  async function handleChoose(number: number) {
    setChoosing(number)
    setError(null)
    try {
      await chooseEnhancementVariant(item.id, number)
      await refresh()
    } catch (err) {
      setError(getHummingErrorMessage(err, 'No se pudo guardar la versión.'))
    } finally {
      setChoosing(null)
    }
  }

  return (
    <li
      className="rounded-lg p-3 flex flex-col gap-3"
      style={{ background: 'var(--bg-card-hover)' }}
    >
      <div className="flex items-center gap-3">
        <div
          className="w-12 h-12 rounded-md shrink-0 overflow-hidden flex items-center justify-center"
          style={{ background: 'var(--color-primary-soft)' }}
        >
          {item.cover_url ? (
            <img src={item.cover_url} alt="" className="w-full h-full object-cover" />
          ) : (
            <Sparkles size={18} style={{ color: 'var(--color-primary)' }} aria-hidden="true" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-white text-sm font-medium truncate">{item.style_label}</p>
          <p className="text-xs text-muted truncate">
            Desde tu versión {versionLabel(item.version_number)}
          </p>
          {busy && (
            <div className="flex items-center gap-2 mt-1">
              <div
                className="h-1.5 rounded-full overflow-hidden flex-1"
                style={{ background: 'var(--bg-card)' }}
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${item.progress}%`, background: 'var(--color-primary)' }}
                />
              </div>
              <span className="text-xs text-muted shrink-0">
                {item.status === 'queued' ? 'En cola' : 'Produciendo versiones…'}
              </span>
            </div>
          )}
          {item.status === 'failed' && (
            <p className="text-xs" style={{ color: 'var(--color-error)' }}>
              {item.error_message ?? 'No se pudo producir.'} No se descontaron créditos.
            </p>
          )}
          {item.status === 'completed' && !chosen && (
            <p className="text-xs text-muted">
              {several
                ? 'Escucha las versiones y elige la que más te guste.'
                : 'Escúchala y guárdala en tu biblioteca.'}
            </p>
          )}
          {item.status === 'completed' && chosen && (
            <p className="text-xs text-success inline-flex items-center gap-1">
              <Check size={12} aria-hidden="true" />
              <Link to="/library" className="underline">
                En tu biblioteca
              </Link>
            </p>
          )}
        </div>
        {busy && <LoaderCircle size={18} className="animate-spin text-muted" aria-hidden="true" />}
      </div>

      {item.status === 'completed' && item.variants.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {item.variants.map((variant) => {
            const playing = track?.id === trackId(variant.number) && isPlaying
            const name = label(variant.number) || item.style_label
            return (
              <div
                key={variant.number}
                className="flex items-center gap-2 rounded-pill pl-1 pr-2 py-1"
                style={{
                  background: 'var(--bg-card)',
                  border: `1px solid ${chosen === variant.number ? 'var(--color-primary)' : 'var(--border-strong)'}`,
                }}
              >
                <button
                  type="button"
                  onClick={() => handlePlay(variant.number)}
                  className="w-8 h-8 rounded-full inline-flex items-center justify-center shrink-0"
                  style={{ background: 'var(--color-primary)', color: 'var(--color-on-primary)' }}
                  aria-label={`${playing ? 'Pausar' : 'Escuchar'} ${item.style_label} ${name}`}
                >
                  {playing ? (
                    <Pause size={14} fill="currentColor" aria-hidden="true" />
                  ) : (
                    <Play size={14} fill="currentColor" aria-hidden="true" />
                  )}
                </button>
                <span className="text-xs text-white">{name}</span>
                {variant.similarity && <SimilarityBadge similarity={variant.similarity} compact />}
                {!chosen && (
                  <button
                    type="button"
                    onClick={() => handleChoose(variant.number)}
                    disabled={choosing !== null}
                    className="text-xs font-medium inline-flex items-center gap-1 disabled:opacity-50"
                    style={{ color: 'var(--color-primary)' }}
                    aria-label={`Elegir ${item.style_label} ${name}`}
                  >
                    {choosing === variant.number ? (
                      <LoaderCircle size={12} className="animate-spin" aria-hidden="true" />
                    ) : (
                      <Check size={12} aria-hidden="true" />
                    )}
                    Elegir
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}

      {error && (
        <p className="text-xs" role="alert" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}
    </li>
  )
}

export default function EnhancePanel({ job, versionLabel, onRequested, refresh }: Props) {
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
    (style !== CUSTOM || customStyle.trim().length > 0)

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
        ...(style === CUSTOM ? { custom_style: customStyle.trim() } : {}),
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

  const chipStyle = (selected: boolean) => ({
    background: selected ? 'var(--color-primary)' : 'var(--bg-card-hover)',
    color: selected ? 'var(--color-on-primary)' : 'var(--text-base)',
    border: `1px solid ${selected ? 'var(--color-primary)' : 'var(--border-strong)'}`,
  })

  return (
    <section
      className="rounded-xl p-5 flex flex-col gap-4"
      style={{
        background: 'var(--color-primary-soft)',
        border: '1px solid var(--color-primary-border)',
      }}
      aria-labelledby="humming-enhance-title"
    >
      <div>
        <h3
          id="humming-enhance-title"
          className="text-white font-semibold inline-flex items-center gap-2"
        >
          <Sparkles size={18} style={{ color: 'var(--color-primary)' }} aria-hidden="true" />
          Mejorar con IA
        </h3>
        <p className="text-muted text-sm mt-1">
          Elige cualquier estilo y la IA rehace tu canción en ese estilo, conservando tu melodía.
          Partimos sola de la versión que más se le parece.
        </p>
      </div>

      {!catalog.available ? (
        <p className="text-sm text-muted">La mejora con IA no está disponible por ahora.</p>
      ) : (
        <>
          <fieldset className="flex flex-col gap-3">
            <legend className="text-white text-sm font-medium mb-2">Estilo</legend>
            {groups.map(([group, styles]) => (
              <div key={group} className="flex flex-col gap-1.5">
                <span className="text-xs text-muted">
                  {group}
                  {styles.some((item) => item.experimental) && ' · experimental'}
                </span>
                <div className="flex flex-wrap gap-2">
                  {styles.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setStyle(item.key)}
                      aria-pressed={style === item.key}
                      className="rounded-pill px-3 py-1.5 text-sm"
                      style={chipStyle(style === item.key)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            <div className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">Otro</span>
              <div className="flex flex-wrap gap-2 items-center">
                <button
                  type="button"
                  onClick={() => setStyle(CUSTOM)}
                  aria-pressed={style === CUSTOM}
                  className="rounded-pill px-3 py-1.5 text-sm"
                  style={chipStyle(style === CUSTOM)}
                >
                  Describir mi estilo
                </button>
                {style === CUSTOM && (
                  <>
                    <label htmlFor="humming-custom-style" className="sr-only">
                      Describe el estilo
                    </label>
                    <input
                      id="humming-custom-style"
                      value={customStyle}
                      onChange={(event) => setCustomStyle(event.target.value)}
                      maxLength={200}
                      placeholder="Ej.: cumbia con sintetizadores y charango"
                      className="flex-1 min-w-[200px] rounded-lg px-3 py-2 text-sm text-white outline-none"
                      style={{
                        background: 'var(--bg-card-hover)',
                        border: '1px solid var(--border-strong)',
                      }}
                    />
                  </>
                )}
              </div>
            </div>
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <legend className="text-white text-sm font-medium mb-2">Fidelidad a tu melodía</legend>
            <div className="flex flex-wrap gap-2">
              {catalog.fidelities.map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFidelity(key)}
                  aria-pressed={fidelity === key}
                  className="rounded-pill px-3 py-1.5 text-sm"
                  style={chipStyle(fidelity === key)}
                >
                  {FIDELITY_LABELS[key]?.label ?? key}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted">{FIDELITY_LABELS[fidelity]?.hint}</p>
          </fieldset>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="rounded-pill px-6 py-2.5 text-sm font-semibold inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ background: 'var(--color-primary)', color: 'var(--color-on-primary)' }}
            >
              {sending ? (
                <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
              ) : (
                <Sparkles size={16} aria-hidden="true" />
              )}
              Mejorar con IA · {cost} crédito{cost === 1 ? '' : 's'}
            </button>
            <span className="text-xs text-muted">
              Recibirás varias versiones para elegir. Tarda de 30 s a 2 minutos.
            </span>
          </div>

          {error && (
            <p className="text-sm" role="alert" style={{ color: 'var(--color-error)' }}>
              {error.message}{' '}
              {error.noCredits && (
                <Link to="/payments" className="underline">
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
