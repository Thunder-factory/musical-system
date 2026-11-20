import { useMemo } from 'react'
import { Link } from 'react-router-dom'

import { Button, FormField, Input } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { TranslationConfig } from '../api/translations.api'
import { LANGUAGE_NAMES } from '../lib/translation-constants'
import TranslationVideoPicker from './translation-video-picker'

interface TranslationFormProps {
  config: TranslationConfig
  file: File | null
  fileError: string | null
  language: string
  title: string
  artist: string
  busy: boolean
  uploading: boolean
  insufficientCredits: boolean
  noCreditsError: boolean
  balance: number
  submitError: string | null
  onFileChange: (file: File | null, error: string | null) => void
  onLanguageChange: (code: string) => void
  onTitleChange: (value: string) => void
  onArtistChange: (value: string) => void
  onSubmit: () => void
}

export default function TranslationForm({
  config,
  file,
  fileError,
  language,
  title,
  artist,
  busy,
  uploading,
  insufficientCredits,
  noCreditsError,
  balance,
  submitError,
  onFileChange,
  onLanguageChange,
  onTitleChange,
  onArtistChange,
  onSubmit,
}: TranslationFormProps) {
  const languageOptions = useMemo(
    () =>
      config.languages.map((item) => ({
        ...item,
        label: LANGUAGE_NAMES[item.code] ?? item.label,
      })),
    [config.languages]
  )

  const canSubmit = Boolean(file) && !busy && !insufficientCredits

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5">
      <TranslationVideoPicker config={config} file={file} disabled={busy} onChange={onFileChange} />

      {fileError && (
        <p className="text-sm text-error" role="alert">
          {fileError}
        </p>
      )}

      <fieldset className="flex flex-col gap-2" disabled={busy}>
        <legend className="mb-1.5 text-xs font-semibold text-muted">Idioma de destino</legend>
        <div className="flex flex-wrap gap-2">
          {languageOptions.map((option) => {
            const selected = option.code === language
            return (
              <button
                key={option.code}
                type="button"
                onClick={() => onLanguageChange(option.code)}
                aria-pressed={selected}
                className={cn(
                  'rounded-full border px-4 py-1.5 text-sm font-medium transition-colors',
                  selected
                    ? 'border-primary bg-primary text-black'
                    : 'border-border-strong bg-card-hover text-white hover:border-primary'
                )}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      </fieldset>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormField label="Título de la canción (opcional)">
          <Input
            value={title}
            onChange={(e) => onTitleChange(e.target.value)}
            maxLength={200}
            disabled={busy}
            placeholder="Ej.: Bohemian Rhapsody"
          />
        </FormField>
        <FormField label="Artista (opcional)">
          <Input
            value={artist}
            onChange={(e) => onArtistChange(e.target.value)}
            maxLength={200}
            disabled={busy}
            placeholder="Ej.: Queen"
          />
        </FormField>
      </div>
      <p className="-mt-2 text-xs text-muted">
        Indicar título y artista ayuda a alinear la letra con mayor precisión.
      </p>

      {(insufficientCredits || noCreditsError) && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-primary-border bg-primary-soft px-4 py-3 text-sm">
          <span className="text-white">
            Necesitas {config.credit_cost} créditos (saldo actual: {balance}).
          </span>
          <Link to="/payments" className="font-semibold text-primary underline">
            Recargar créditos
          </Link>
        </div>
      )}

      <div className="flex items-center justify-between gap-3 pt-1">
        <span className="text-xs text-muted">Tiempo estimado: 1–4 min</span>
        <Button
          onClick={onSubmit}
          disabled={!canSubmit}
          loading={busy}
          costCredits={config.credit_cost}
        >
          {uploading ? 'Subiendo…' : busy ? 'Traduciendo…' : 'Traducir video'}
        </Button>
      </div>

      {submitError && !noCreditsError && (
        <p className="text-sm text-error" role="alert">
          {submitError}
        </p>
      )}
    </div>
  )
}
