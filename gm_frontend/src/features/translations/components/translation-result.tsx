import { useEffect, useState } from 'react'
import { Download, LoaderCircle, Mic2 } from 'lucide-react'

import { Button } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import {
  getTranslationFileUrl,
  type TranslationFileKind,
  type TranslationJob,
} from '../api/translations.api'
import { formatDuration, LANGUAGE_NAMES } from '../lib/translation-constants'

function triggerDownload(url: string, filename: string) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export default function TranslationResult({ job }: { job: TranslationJob }) {
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [videoError, setVideoError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<TranslationFileKind | null>(null)

  useEffect(() => {
    let cancelled = false
    setVideoUrl(null)
    setVideoError(null)
    getTranslationFileUrl(job.id, 'video')
      .then((url) => {
        if (!cancelled) {
          setVideoUrl(url)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setVideoError('No se pudo cargar el video.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [job.id])

  async function handleDownload(kind: TranslationFileKind) {
    setDownloading(kind)
    try {
      const url = await getTranslationFileUrl(job.id, kind, true)
      const baseName = job.song_title || job.source_filename || 'traduccion'
      triggerDownload(url, `${baseName}.${kind === 'video' ? 'mp4' : 'mp3'}`)
    } catch {
      toast.error('No se pudo iniciar la descarga')
    } finally {
      setDownloading(null)
    }
  }

  const lyrics = job.lyrics
  const showOriginal = Boolean(lyrics?.frases.some((phrase) => phrase.original))

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5">
      <div className="flex aspect-video items-center justify-center overflow-hidden rounded-xl bg-black">
        {videoUrl ? (
          <video src={videoUrl} controls playsInline className="h-full w-full" />
        ) : videoError ? (
          <p className="text-sm text-error">{videoError}</p>
        ) : (
          <LoaderCircle className="animate-spin text-muted" aria-label="Cargando video" />
        )}
      </div>

      <div className="flex flex-wrap gap-2.5">
        <Button
          loading={downloading === 'video'}
          onClick={() => void handleDownload('video')}
          leftIcon={<Download size={16} aria-hidden="true" />}
        >
          Descargar video
        </Button>
        <Button
          variant="secondary"
          loading={downloading === 'audio'}
          onClick={() => void handleDownload('audio')}
          leftIcon={<Mic2 size={16} aria-hidden="true" />}
        >
          Solo la voz (MP3)
        </Button>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <dt className="text-muted">Idiomas</dt>
        <dd className="text-white">
          {LANGUAGE_NAMES[lyrics?.idioma_origen ?? ''] ?? lyrics?.idioma_origen ?? '—'} →{' '}
          {LANGUAGE_NAMES[job.target_language] ?? job.target_language}
        </dd>
        <dt className="text-muted">Duración</dt>
        <dd className="tabular-nums text-white">{formatDuration(job.source_duration_seconds)}</dd>
        {typeof job.details.segundos_proceso === 'number' && (
          <>
            <dt className="text-muted">Tiempo de proceso</dt>
            <dd className="tabular-nums text-white">
              {formatDuration(job.details.segundos_proceso)}
            </dd>
          </>
        )}
        <dt className="text-muted">Créditos</dt>
        <dd className="tabular-nums text-white">{job.credits_used}</dd>
      </dl>

      {lyrics && lyrics.frases.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-white">Letra traducida</h3>
          {lyrics.resumen && <p className="text-xs italic text-muted">{lyrics.resumen}</p>}
          <div className="max-h-72 overflow-y-auto rounded-xl border border-border">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card-hover">
                <tr className="text-left text-muted">
                  <th className="w-16 px-3 py-2 font-medium">Tiempo</th>
                  {showOriginal && <th className="px-3 py-2 font-medium">Original</th>}
                  <th className="px-3 py-2 font-medium">Traducción</th>
                </tr>
              </thead>
              <tbody>
                {lyrics.frases.map((phrase, index) => (
                  <tr key={index} className="border-t border-border">
                    <td className="px-3 py-2 tabular-nums text-muted">
                      {formatDuration(phrase.inicio)}
                    </td>
                    {showOriginal && (
                      <td className="px-3 py-2 text-muted">{phrase.original ?? ''}</td>
                    )}
                    <td className="px-3 py-2 text-white">{phrase.texto}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
