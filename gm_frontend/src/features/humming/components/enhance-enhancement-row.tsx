import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, LoaderCircle, Pause, Play, Sparkles } from 'lucide-react'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { cn } from '../../../lib/cn'
import { toast } from '../../../store/toast.store'
import {
  chooseEnhancementVariant,
  getHummingErrorMessage,
  type HummingEnhancement,
  type HummingJob,
} from '../api/humming.api'
import SimilarityBadge from './similarity-badge'

const VARIANT_LETTERS = ['A', 'B', 'C']

interface EnhancementRowProps {
  item: HummingEnhancement
  job: HummingJob
  refresh: () => Promise<HummingJob | null>
  versionLabel: (number: number) => string
}

export default function EnhancementRow({
  item,
  job,
  refresh,
  versionLabel,
}: EnhancementRowProps) {
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
    const fresh = await refresh().catch(() => null)
    const latest = fresh?.enhancements.find((e) => e.id === item.id) ?? item
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
      toast.success('Versión guardada en tu biblioteca')
    } catch (err) {
      setError(getHummingErrorMessage(err, 'No se pudo guardar la versión.'))
    } finally {
      setChoosing(null)
    }
  }

  return (
    <li className="flex flex-col gap-3 rounded-xl bg-card-hover p-3">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-md bg-primary-soft">
          {item.cover_url ? (
            <img src={item.cover_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <Sparkles size={18} className="text-primary" aria-hidden="true" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">{item.style_label}</p>
          <p className="truncate text-xs text-muted">
            Desde tu versión {versionLabel(item.version_number)}
          </p>
          {busy && (
            <div className="mt-1 flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-card">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${item.progress}%` }}
                />
              </div>
              <span className="shrink-0 text-xs text-muted">
                {item.status === 'queued' ? 'En cola' : 'Produciendo versiones…'}
              </span>
            </div>
          )}
          {item.status === 'failed' && (
            <p className="text-xs text-error">
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
            <p className="inline-flex items-center gap-1 text-xs text-success">
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
                className={cn(
                  'flex items-center gap-2 rounded-full border bg-card py-1 pl-1 pr-2.5',
                  chosen === variant.number ? 'border-primary' : 'border-border-strong'
                )}
              >
                <button
                  type="button"
                  onClick={() => void handlePlay(variant.number)}
                  aria-label={`${playing ? 'Pausar' : 'Escuchar'} ${item.style_label} ${name}`}
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-black"
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
                    onClick={() => void handleChoose(variant.number)}
                    disabled={choosing !== null}
                    aria-label={`Elegir ${item.style_label} ${name}`}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-hover disabled:opacity-50"
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
        <p className="text-xs text-error" role="alert">
          {error}
        </p>
      )}
    </li>
  )
}
