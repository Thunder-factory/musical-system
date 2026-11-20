import { useCallback, useEffect, useState } from 'react'
import { Download, LoaderCircle, Pause, Play } from 'lucide-react'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { getStemDownloadUrl, type StemFile } from '../api/stems.api'

const STEM_LABELS: Record<string, string> = {
  vocals: 'Voz',
  no_vocals: 'Karaoke (sin voz)',
  bass: 'Bajo',
  drums: 'Batería',
  other: 'Otros',
}

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return '0:00'
  }
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

export default function StemTrackRow({
  stemFile,
  active,
  onActivate,
}: {
  stemFile: StemFile
  active: boolean
  onActivate: () => void
}) {
  const [url, setUrl] = useState<string | null>(null)
  const [loadingUrl, setLoadingUrl] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const {
    track: globalTrack,
    isPlaying: globalIsPlaying,
    currentTime,
    duration: globalDuration,
    playTrack,
    pause,
    seek,
  } = useGlobalAudioPlayer()

  const trackId = `stem:${stemFile.id}`
  const isActiveTrack = globalTrack?.id === trackId
  const isPlaying = isActiveTrack && globalIsPlaying
  const trackCurrentTime = isActiveTrack ? currentTime : 0
  const duration = isActiveTrack ? globalDuration : (stemFile.duration_seconds ?? 0)
  const stemTitle = STEM_LABELS[stemFile.stem_type] ?? stemFile.stem_type

  const loadUrl = useCallback(async () => {
    setLoadingUrl(true)
    setError(null)
    try {
      const presigned = await getStemDownloadUrl(stemFile.id)
      setUrl(presigned)
      return presigned
    } catch {
      setError('No se pudo cargar el audio.')
      return null
    } finally {
      setLoadingUrl(false)
    }
  }, [stemFile.id])

  useEffect(() => {
    void loadUrl()
  }, [loadUrl])

  async function handlePlay() {
    if (loadingUrl) {
      return
    }
    onActivate()
    setError(null)
    if (isActiveTrack) {
      if (isPlaying) {
        pause()
      } else if (url) {
        playTrack({ id: trackId, audioUrl: url, title: stemTitle, subtitle: 'Pista separada' })
      }
      return
    }
    const presignedUrl = url ?? (await loadUrl())
    if (!presignedUrl) {
      return
    }
    playTrack({ id: trackId, audioUrl: presignedUrl, title: stemTitle, subtitle: 'Pista separada' })
  }

  async function handleDownload() {
    setError(null)
    try {
      const presigned = await getStemDownloadUrl(stemFile.id, true)
      const link = document.createElement('a')
      link.href = presigned
      link.download = `${stemFile.stem_type}.wav`
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch {
      setError('No se pudo preparar la descarga.')
    }
  }

  const safeDuration = duration > 0 ? duration : 1

  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-xl border bg-card-hover px-4 py-3',
        active ? 'border-primary-border' : 'border-transparent'
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-white">{stemTitle}</p>
          <p className="text-xs tabular-nums text-muted">
            {formatTime(trackCurrentTime)} / {formatTime(duration)}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button
            size="sm"
            onClick={() => void handlePlay()}
            disabled={loadingUrl}
            aria-label={isPlaying ? `Pausar ${stemTitle}` : `Reproducir ${stemTitle}`}
            leftIcon={
              loadingUrl ? (
                <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
              ) : isPlaying ? (
                <Pause size={14} fill="currentColor" aria-hidden="true" />
              ) : (
                <Play size={14} fill="currentColor" aria-hidden="true" />
              )
            }
          >
            {isPlaying ? 'Pausar' : 'Reproducir'}
          </Button>
          <button
            type="button"
            onClick={() => void handleDownload()}
            aria-label={`Descargar ${stemTitle}`}
            title="Descargar"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-white transition-colors hover:bg-white/20"
          >
            <Download size={14} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-[11px] tabular-nums text-muted">{formatTime(trackCurrentTime)}</span>
        <input
          type="range"
          min={0}
          max={safeDuration}
          step={0.1}
          value={Math.min(trackCurrentTime, safeDuration)}
          onChange={(event) => {
            if (isActiveTrack) {
              seek(Number(event.target.value))
            }
          }}
          aria-label={`Progreso de ${stemTitle}`}
          className="min-w-0 flex-1 accent-[var(--color-primary)]"
        />
        <span className="text-[11px] tabular-nums text-muted">{formatTime(duration)}</span>
      </div>

      {error && (
        <p className="text-xs text-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
