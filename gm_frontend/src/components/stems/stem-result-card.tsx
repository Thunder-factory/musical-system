import { useCallback, useEffect, useRef, useState } from 'react'
import { Download, LoaderCircle, Pause, Play } from 'lucide-react'
import type { StemFile } from '../../api/modules/stems.api'
import { getStemDownloadUrl } from '../../api/modules/stems.api'

const STEM_LABELS: Record<string, string> = {
  vocals: 'Voz',
  no_vocals: 'Karaoke (sin voz)',
  bass: 'Bajo',
  drums: 'Batería',
  other: 'Otros',
}

interface Props {
  stemFiles: StemFile[]
  sourceFilename?: string
  createdAt?: string
}

interface StemTrackProps {
  stemFile: StemFile
  active: boolean
  onActivate: () => void
}

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return '0:00'
  }

  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

function StemTrack({ stemFile, active, onActivate }: StemTrackProps) {
  const [url, setUrl] = useState<string | null>(null)
  const [loadingUrl, setLoadingUrl] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(stemFile.duration_seconds ?? 0)
  const [error, setError] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  useEffect(() => {
    if (!active && audioRef.current) {
      audioRef.current.pause()
      setIsPlaying(false)
    }
  }, [active])

  const loadUrl = useCallback(async () => {
    setLoadingUrl(true)
    setError(null)
    try {
      const presigned = await getStemDownloadUrl(stemFile.id)
      const audio = audioRef.current
      if (audio) {
        audio.src = presigned
        audio.load()
      }
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
    const audio = audioRef.current
    if (!audio || loadingUrl) {
      return
    }

    onActivate()
    setError(null)

    if (isPlaying) {
      audio.pause()
      return
    }

    if (!url) {
      if (!loadingUrl) {
        void loadUrl()
      }
      setError('El audio se está preparando. Presiona reproducir cuando termine.')
      return
    }

    try {
      await audio.play()
      setIsPlaying(true)
    } catch {
      setError('El navegador bloqueó la reproducción. Presiona reproducir nuevamente.')
      setIsPlaying(false)
    }
  }

  async function handleDownload() {
    setError(null)
    try {
      const presigned = await getStemDownloadUrl(stemFile.id, true)
      const link = document.createElement('a')
      link.href = presigned
      link.download = `${stemFile.stem_type}.wav`
      link.click()
    } catch {
      setError('No se pudo preparar la descarga.')
    }
  }

  const safeDuration = duration > 0 ? duration : 1
  const progress = Math.min(100, Math.max(0, (currentTime / safeDuration) * 100))

  return (
    <div
      className="bg-card-hover rounded-lg px-4 py-3 flex flex-col gap-3"
      style={{ border: `1px solid ${active ? 'var(--color-primary-soft)' : 'transparent'}` }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-white text-sm font-medium truncate">
            {STEM_LABELS[stemFile.stem_type] ?? stemFile.stem_type}
          </p>
          <p className="text-muted text-xs">
            {formatTime(currentTime)} / {formatTime(duration)}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handlePlay}
            disabled={loadingUrl}
            aria-label={
              isPlaying
                ? `Pausar ${STEM_LABELS[stemFile.stem_type]}`
                : `Reproducir ${STEM_LABELS[stemFile.stem_type]}`
            }
            title={loadingUrl ? 'Cargando audio' : isPlaying ? 'Pausar' : 'Reproducir'}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all hover:brightness-110 hover:-translate-y-px disabled:hover:translate-y-0 disabled:hover:brightness-100"
            style={{
              background: 'var(--color-primary)',
              color: 'var(--bg-base)',
              opacity: loadingUrl ? 0.5 : 1,
            }}
          >
            {loadingUrl ? (
              <LoaderCircle size={14} aria-hidden="true" className="animate-spin" />
            ) : isPlaying ? (
              <Pause size={14} fill="currentColor" aria-hidden="true" />
            ) : (
              <Play size={14} fill="currentColor" aria-hidden="true" />
            )}
            Reproducir
          </button>
          <button
            type="button"
            onClick={handleDownload}
            aria-label={`Descargar ${STEM_LABELS[stemFile.stem_type]}`}
            title="Descargar"
            className="flex h-7 w-7 items-center justify-center rounded-md text-white transition-all hover:brightness-110 hover:-translate-y-px"
            style={{ background: 'var(--bg-white-soft)' }}
          >
            <Download size={14} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-muted text-[11px]">{formatTime(currentTime)}</span>
        <input
          type="range"
          min={0}
          max={safeDuration}
          step={0.1}
          value={Math.min(currentTime, safeDuration)}
          onChange={(event) => {
            const nextTime = Number(event.target.value)
            if (audioRef.current) {
              audioRef.current.currentTime = nextTime
            }
            setCurrentTime(nextTime)
          }}
          aria-label={`Progreso de ${STEM_LABELS[stemFile.stem_type]}`}
          className="min-w-0 flex-1 accent-[var(--color-primary)]"
          style={{
            background: `linear-gradient(to right, var(--color-primary) ${progress}%, var(--bg-card-hover) ${progress}%)`,
          }}
        />
        <span className="text-muted text-[11px]">{formatTime(duration)}</span>
      </div>

      {error && (
        <p className="text-xs" style={{ color: 'var(--color-error)' }}>
          {error}
        </p>
      )}

      <audio
        ref={audioRef}
        src={url ?? undefined}
        preload="metadata"
        onLoadedMetadata={(event) => {
          if (Number.isFinite(event.currentTarget.duration)) {
            setDuration(event.currentTarget.duration)
          }
        }}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => {
          setIsPlaying(false)
          setCurrentTime(0)
        }}
        className="sr-only"
      />
    </div>
  )
}

export default function StemResultCard({ stemFiles, sourceFilename, createdAt }: Props) {
  const [activeStemId, setActiveStemId] = useState<string | null>(null)

  if (stemFiles.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className="rounded-lg px-4 py-3"
        style={{
          background: 'var(--bg-card-hover)',
          border: '1px solid var(--color-primary-soft)',
        }}
      >
        <p className="text-muted text-xs">Resultado de separación</p>
        <p className="text-white text-sm font-semibold truncate" title={sourceFilename}>
          {sourceFilename ?? 'Archivo de audio'}
        </p>
        <p className="text-muted text-xs mt-1">
          {createdAt ? new Date(createdAt).toLocaleString() : 'Pistas disponibles'} ·{' '}
          {stemFiles.length} pistas
        </p>
      </div>
      {stemFiles.map((stemFile) => (
        <StemTrack
          key={stemFile.id}
          stemFile={stemFile}
          active={activeStemId === stemFile.id}
          onActivate={() => setActiveStemId(stemFile.id)}
        />
      ))}
    </div>
  )
}
