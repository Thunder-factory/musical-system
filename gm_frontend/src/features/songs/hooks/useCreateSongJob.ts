import { useCallback, useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'
import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import { toast } from '../../../store/toast.store'
import {
  generateSong,
  getSongJob,
  getSongJobs,
  getSongPlayUrl,
  getSongThumbnailUrl,
  type GenerateSongPayload,
  type JobStatus,
} from '../api/songs.api'
import type { GenerationStage, ReadySongPreview } from '../components/create-preview-card'

const POLLING_INTERVAL_MS = 5_000

export function useCreateSongJob(title: string, onRecoverTitle?: (title: string) => void) {
  const upsertJob = useActiveJobsStore((s) => s.upsertJob)
  const removeJob = useActiveJobsStore((s) => s.removeJob)
  const { playTrack, close, track: globalTrack } = useGlobalAudioPlayer()

  const [stage, setStage] = useState<GenerationStage>('idle')
  const [ready, setReady] = useState<ReadySongPreview | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const activeJobIdRef = useRef<string | null>(null)
  const titleRef = useRef(title)

  useEffect(() => {
    titleRef.current = title
  }, [title])

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const handleJobStatus = useCallback(
    async (status: JobStatus, songId: string, jobId: string) => {
      if (status === 'no_credits') {
        stopPolling()
        removeJob(jobId)
        setStage('no_credits')
        void refreshAuthBalance()
        return
      }
      if (status === 'ready') {
        stopPolling()
        removeJob(jobId)
        void refreshAuthBalance()
        try {
          const [playUrl, thumbnailUrl] = await Promise.all([
            getSongPlayUrl(songId),
            getSongThumbnailUrl(songId).catch(() => ''),
          ])
          setReady({ songId, playUrl, thumbnailUrl })
          playTrack({
            id: `song:${songId}`,
            audioUrl: playUrl,
            title: titleRef.current.trim() || 'Tu canción',
            coverUrl: thumbnailUrl || null,
          })
          setStage('ready')
          toast.success('¡Tu canción está lista!', 'Ya puedes escucharla y verla en tu biblioteca.')
        } catch {
          setStage('error')
          setErrorMsg('La canción está lista, pero no se pudo cargar el audio.')
        }
        return
      }
      if (status === 'error') {
        stopPolling()
        removeJob(jobId)
        setStage('error')
        setErrorMsg('El servidor reportó un error al generar la canción.')
        void refreshAuthBalance()
      }
    },
    [playTrack, removeJob, stopPolling]
  )

  const startPolling = useCallback(
    (jobId: string, songId: string, label: string) => {
      stopPolling()
      activeJobIdRef.current = jobId
      setStage('polling')
      upsertJob({ id: jobId, kind: 'song', label, route: '/create', status: 'processing' })
      pollingRef.current = setInterval(async () => {
        try {
          const job = await getSongJob(jobId)
          await handleJobStatus(job.status, songId, jobId)
        } catch {
          stopPolling()
          removeJob(jobId)
          setStage('error')
          setErrorMsg('Error al consultar el estado de la generación.')
        }
      }, POLLING_INTERVAL_MS)
    },
    [handleJobStatus, removeJob, stopPolling, upsertJob]
  )

  useEffect(() => {
    let cancelled = false
    getSongJobs(true)
      .then((jobs) => {
        if (cancelled || jobs.length === 0) {
          return
        }
        const active = jobs.find((j) => j.song_id && (j.status === 'queued' || j.status === 'processing'))
        if (active?.song_id) {
          const label = active.title || active.song_title || 'Tu canción'
          if (!titleRef.current.trim() && label) {
            onRecoverTitle?.(label)
          }
          startPolling(active.id, active.song_id, label)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
      stopPolling()
    }
  }, [onRecoverTitle, startPolling, stopPolling])

  async function submitGeneration(payload: GenerateSongPayload) {
    setErrorMsg(null)
    setReady(null)
    setStage('submitting')
    try {
      const res = await generateSong(payload)
      const label = payload.title?.trim() || 'Tu canción'
      upsertJob({ id: res.job_id, kind: 'song', label, route: '/create', status: 'queued' })
      void refreshAuthBalance()

      const firstCheck = await getSongJob(res.job_id)
      if (firstCheck.status === 'ready' || firstCheck.status === 'no_credits') {
        await handleJobStatus(firstCheck.status, res.song_id, res.job_id)
      } else {
        startPolling(res.job_id, res.song_id, label)
      }
    } catch (err: unknown) {
      if (isAxiosError(err) && err.response?.status === 402) {
        setStage('no_credits')
      } else {
        setStage('error')
        setErrorMsg('No se pudo iniciar la generación. Intenta de nuevo.')
      }
    }
  }

  function resetJob() {
    stopPolling()
    if (activeJobIdRef.current) {
      removeJob(activeJobIdRef.current)
      activeJobIdRef.current = null
    }
    if (ready && globalTrack?.id === `song:${ready.songId}`) {
      close()
    }
    setStage('idle')
    setReady(null)
    setErrorMsg(null)
  }

  return { stage, ready, errorMsg, setErrorMsg, submitGeneration, resetJob }
}
