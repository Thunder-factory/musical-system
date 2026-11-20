import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, FileMusic } from 'lucide-react'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { toast } from '../../../store/toast.store'
import {
  chooseHummingVersion,
  getHummingErrorMessage,
  type HummingJob,
  type HummingVersion,
} from '../api/humming.api'
import { styleLabel } from '../lib/humming-constants'
import EnhancePanel from './enhance-panel'
import { HummingAiProgress, HummingInitialProgress } from './humming-progress-banner'
import { HummingVersionCard } from './humming-version-card'
import MelodyChart from './melody-chart'
import { SIMILARITY_EXPLANATION } from './similarity-badge'

interface HummingVersionsGridProps {
  job: HummingJob
  onChosen: () => void
  onEnhanceRequested: () => void
  refresh: () => Promise<HummingJob | null>
}

export default function HummingVersionsGrid({
  job,
  onChosen,
  onEnhanceRequested,
  refresh,
}: HummingVersionsGridProps) {
  const { track, isPlaying, playTrack, pause } = useGlobalAudioPlayer()
  const [choosing, setChoosing] = useState<number | null>(null)
  const [chooseError, setChooseError] = useState<string | null>(null)

  const working = job.status === 'queued' || job.status === 'processing'

  if (working && job.versions.length === 0) {
    return <HummingInitialProgress job={job} />
  }

  if (job.status === 'failed') {
    return (
      <div
        className="flex flex-col gap-1 rounded-xl border border-error-border bg-error-soft px-4 py-4"
        role="alert"
      >
        <p className="text-sm font-semibold text-white">
          No pudimos crear canciones con este tarareo
        </p>
        <p className="text-sm text-white/80">{job.error_message ?? 'Intenta grabarlo de nuevo.'}</p>
        <p className="text-xs text-muted">No se descontaron créditos.</p>
      </div>
    )
  }

  async function handlePlay(version: HummingVersion) {
    const trackId = `humming:${job.id}:${version.number}`
    if (track?.id === trackId && isPlaying) {
      pause()
      return
    }
    const fresh = await refresh().catch(() => null)
    const latest = fresh?.versions.find((item) => item.number === version.number) ?? version
    const conIa = latest.ai?.status === 'completed' && latest.ai.audio_url
    playTrack({
      id: trackId,
      audioUrl: conIa ? (latest.ai?.audio_url as string) : latest.audio_url,
      title: job.title || 'Tu tarareo',
      subtitle: `${styleLabel(version.style)}${conIa ? ' · producida con IA' : ''}`,
      coverUrl: conIa ? latest.ai?.cover_url : null,
    })
  }

  async function handleChoose(version: HummingVersion) {
    setChoosing(version.number)
    setChooseError(null)
    try {
      await chooseHummingVersion(job.id, version.number, job.title)
      await refresh()
      toast.success('Versión guardada en tu biblioteca')
      onChosen()
    } catch (error) {
      setChooseError(getHummingErrorMessage(error, 'No se pudo guardar la versión.'))
    } finally {
      setChoosing(null)
    }
  }

  const meta = job.metadata

  return (
    <div className="flex flex-col gap-5">
      <HummingAiProgress job={job} />

      <div className="flex flex-col gap-2">
        {meta.estiloMensaje && <p className="font-medium text-white">{meta.estiloMensaje}</p>}
        <dl className="flex flex-wrap gap-2 text-xs">
          {meta.bpm !== undefined && (
            <div className="rounded-full bg-card-hover px-3 py-1">
              <dt className="sr-only">Tempo</dt>
              <dd className="text-white">{Math.round(meta.bpm)} BPM</dd>
            </div>
          )}
          {meta.tonalidad && (
            <div className="rounded-full bg-card-hover px-3 py-1">
              <dt className="sr-only">Tonalidad</dt>
              <dd className="text-white">{meta.tonalidad}</dd>
            </div>
          )}
          {meta.acordes && meta.acordes.length > 0 && (
            <div className="rounded-full bg-card-hover px-3 py-1">
              <dt className="sr-only">Acordes</dt>
              <dd className="text-white">{meta.acordes.join(' · ')}</dd>
            </div>
          )}
        </dl>
      </div>

      {meta.grafico && <MelodyChart chart={meta.grafico} />}

      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
        {job.versions.map((version) => (
          <HummingVersionCard
            key={version.number}
            job={job}
            version={version}
            playing={track?.id === `humming:${job.id}:${version.number}` && isPlaying}
            choosing={choosing === version.number}
            onPlay={() => void handlePlay(version)}
            onChoose={() => void handleChoose(version)}
          />
        ))}
      </div>

      {job.versions.some((v) => v.ai?.similarity) && (
        <p className="text-xs text-muted">
          <span className="text-white">Parecido con tu melodía:</span> {SIMILARITY_EXPLANATION}
        </p>
      )}

      {chooseError && (
        <p className="text-sm text-error" role="alert">
          {chooseError}
        </p>
      )}

      <p className="text-sm text-muted">
        {job.song_id ? (
          <>
            Guardamos tu versión elegida.{' '}
            <Link to="/library" className="text-primary underline hover:text-primary-hover">
              Ver en la biblioteca
            </Link>
          </>
        ) : (
          'Escucha las versiones y elige la que más te guste para guardarla en tu biblioteca.'
        )}
      </p>

      {(job.downloads.score_musicxml_url || job.downloads.melody_midi_url) && (
        <div className="flex flex-wrap gap-4 text-sm">
          {job.downloads.score_musicxml_url && (
            <a
              href={job.downloads.score_musicxml_url}
              download
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-muted hover:text-white"
            >
              <FileMusic size={16} aria-hidden="true" /> Partitura (MusicXML)
            </a>
          )}
          {job.downloads.melody_midi_url && (
            <a
              href={job.downloads.melody_midi_url}
              download
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-muted hover:text-white"
            >
              <Download size={16} aria-hidden="true" /> Melodía (MIDI)
            </a>
          )}
        </div>
      )}

      {job.status === 'completed' && (
        <EnhancePanel
          job={job}
          refresh={refresh}
          onRequested={onEnhanceRequested}
          versionLabel={(number) => {
            const version = job.versions.find((item) => item.number === number)
            return `${number} (${styleLabel(version?.style)})`
          }}
        />
      )}
    </div>
  )
}
