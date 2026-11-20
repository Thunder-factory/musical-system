import { useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'
import { useNavigate } from 'react-router-dom'

import { refreshAuthBalance, useActiveJobsStore } from '../../../store/active-jobs.store'
import type { KaraokeGenerateResult } from '../../../types'
import { generateKaraoke, pollKaraokeStatus } from '../api/karaoke.api'

export const KARAOKE_STEPS = [
  'Separando pistas de audio',
  'Transcribiendo letra',
  'Sincronizando tiempos',
]

export type GenerateStage = 'confirm' | 'generating' | 'no_credits' | 'error' | 'timeout'

const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 15 * 60 * 1000

function stageToStep(stage: KaraokeGenerateResult['processing_stage']): number {
  if (stage === 'transcribing') {
    return 1
  }
  if (stage === 'synchronizing') {
    return 2
  }
  if (stage === 'completed') {
    return KARAOKE_STEPS.length
  }
  return 0
}

export function useKaraokeGeneration(
  songId: string | undefined,
  songTitle: string,
  source?: string
) {
  const navigate = useNavigate()
  const { upsertJob, removeJob } = useActiveJobsStore()

  const [stage, setStage] = useState<GenerateStage>('confirm')
  const [activeStep, setActiveStep] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const isMountedRef = useRef(true)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const operationRef = useRef(0)

  useEffect(() => {
    return () => {
      isMountedRef.current = false
      operationRef.current += 1
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current)
      }
    }
  }, [])

  function cancelAndGoBack() {
    operationRef.current += 1
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
    navigate('/karaoke')
  }

  function reset() {
    setStage('confirm')
    setActiveStep(0)
    setErrorMessage(null)
  }

  async function start() {
    if (!songId) {
      return
    }
    const opId = operationRef.current + 1
    operationRef.current = opId
    setStage('generating')
    setActiveStep(0)
    setErrorMessage(null)

    const isCurrent = () => isMountedRef.current && operationRef.current === opId
    const waitNext = () =>
      new Promise<void>((resolve) => {
        pollTimerRef.current = setTimeout(() => {
          pollTimerRef.current = null
          resolve()
        }, POLL_INTERVAL_MS)
      })

    let jobKey: string | null = null
    try {
      const result = await generateKaraoke(songId)
      if (!isCurrent()) {
        return
      }
      jobKey = `karaoke:${result.karaoke_id}`
      upsertJob({
        id: jobKey,
        kind: 'song',
        label: `Karaoke: ${songTitle}`,
        route: '/karaoke',
        status: 'processing',
      })
      void refreshAuthBalance()

      let status = result.status
      let processingStage = result.processing_stage
      const startedAt = Date.now()
      while (status !== 'ready' && status !== 'failed') {
        if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
          setStage('timeout')
          return
        }
        setActiveStep(stageToStep(processingStage))
        await waitNext()
        if (!isCurrent()) {
          return
        }
        const poll = await pollKaraokeStatus(result.karaoke_id)
        if (poll.status === 'failed') {
          throw new Error(poll.error_message ?? 'No se pudo completar la generación del karaoke.')
        }
        status = poll.status
        processingStage = poll.processing_stage
        setActiveStep(stageToStep(processingStage))
      }
      if (status === 'failed') {
        throw new Error('No se pudo completar la generación del karaoke.')
      }
      if (!isCurrent()) {
        return
      }
      setActiveStep(KARAOKE_STEPS.length)
      removeJob(jobKey)
      void refreshAuthBalance()
      navigate(`/karaoke/play/${result.karaoke_id}`, {
        replace: true,
        state: { songId, songTitle, source },
      })
    } catch (err) {
      if (jobKey) {
        removeJob(jobKey)
      }
      void refreshAuthBalance()
      if (!isCurrent()) {
        return
      }
      if (isAxiosError(err) && err.response?.status === 402) {
        setStage('no_credits')
      } else {
        setErrorMessage(err instanceof Error ? err.message : null)
        setStage('error')
      }
    }
  }

  return { stage, activeStep, errorMessage, start, reset, cancelAndGoBack }
}
