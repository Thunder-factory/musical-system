import { useEffect, useState } from 'react'

import { getTranslationJob } from '../api/modules/translations.api'
import type { TranslationJob } from '../api/modules/translations.api'

const FINAL_STATES = ['completed', 'failed']
const POLL_MS = 3000
const RETRY_MS = 6000

/**
 * Consulta el estado de una traducción cada 3 segundos hasta que termina.
 *
 * @param jobId - ID del TranslationJob a seguir, o null si no hay ninguno seleccionado.
 */
export function useTranslationJob(jobId: string | null) {
  const [job, setJob] = useState<TranslationJob | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setJob(null)
    setLoading(Boolean(jobId))
    if (!jobId) {
      return
    }

    let cancelled = false
    let timeout: ReturnType<typeof setTimeout> | null = null

    const poll = async () => {
      try {
        const data = await getTranslationJob(jobId)
        if (cancelled) {return}
        setJob(data)
        setLoading(false)
        if (!FINAL_STATES.includes(data.status)) {
          timeout = setTimeout(poll, POLL_MS)
        }
      } catch {
        if (!cancelled) {
          timeout = setTimeout(poll, RETRY_MS)
        }
      }
    }

    poll()
    return () => {
      cancelled = true
      if (timeout) {clearTimeout(timeout)}
    }
  }, [jobId])

  return { job, loading }
}
