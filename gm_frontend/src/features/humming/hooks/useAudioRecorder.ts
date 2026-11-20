import { useCallback, useEffect, useRef, useState } from 'react'

export type RecorderState = 'idle' | 'requesting' | 'recording' | 'recorded'

export interface Recording {
  file: File
  url: string
  seconds: number
}

const MIME_CANDIDATES: { mime: string; ext: string }[] = [
  { mime: 'audio/webm;codecs=opus', ext: 'webm' },
  { mime: 'audio/webm', ext: 'webm' },
  { mime: 'audio/ogg;codecs=opus', ext: 'ogg' },
  { mime: 'audio/mp4', ext: 'm4a' },
]

function pickMime(): { mime: string; ext: string } | null {
  if (typeof MediaRecorder === 'undefined') {
    return null
  }
  return MIME_CANDIDATES.find(({ mime }) => MediaRecorder.isTypeSupported(mime)) ?? null
}

export function useAudioRecorder(maxSeconds: number) {
  const [state, setState] = useState<RecorderState>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [recording, setRecording] = useState<Recording | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startedAtRef = useRef(0)
  const urlRef = useRef<string | null>(null)

  const releaseStream = useCallback(() => {
    if (tickRef.current) {
      clearInterval(tickRef.current)
      tickRef.current = null
    }
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }, [])

  const revokeUrl = useCallback(() => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
  }, [])

  const stop = useCallback(() => {
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
    }
  }, [])

  const start = useCallback(async () => {
    const format = pickMime()
    if (!format || !navigator.mediaDevices?.getUserMedia) {
      setError('Tu navegador no permite grabar audio. Puedes subir un archivo en su lugar.')
      return
    }

    setError(null)
    setState('requesting')
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true },
      })
    } catch {
      setState('idle')
      setError('No pudimos acceder al micrófono. Revisa los permisos del navegador.')
      return
    }

    revokeUrl()
    setRecording(null)
    streamRef.current = stream
    const chunks: Blob[] = []
    const recorder = new MediaRecorder(stream, { mimeType: format.mime })
    recorderRef.current = recorder

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunks.push(event.data)
      }
    }
    recorder.onstop = () => {
      releaseStream()
      const seconds = (performance.now() - startedAtRef.current) / 1000
      const blob = new Blob(chunks, { type: format.mime.split(';')[0] })
      const file = new File([blob], `tarareo.${format.ext}`, { type: blob.type })
      const url = URL.createObjectURL(blob)
      urlRef.current = url
      setElapsed(Math.min(seconds, maxSeconds))
      setRecording({ file, url, seconds })
      setState('recorded')
    }

    startedAtRef.current = performance.now()
    setElapsed(0)
    recorder.start()
    setState('recording')
    tickRef.current = setInterval(() => {
      const seconds = (performance.now() - startedAtRef.current) / 1000
      setElapsed(seconds)
      if (seconds >= maxSeconds) {
        stop()
      }
    }, 100)
  }, [maxSeconds, releaseStream, revokeUrl, stop])

  const reset = useCallback(() => {
    stop()
    releaseStream()
    revokeUrl()
    setRecording(null)
    setElapsed(0)
    setError(null)
    setState('idle')
  }, [releaseStream, revokeUrl, stop])

  useEffect(
    () => () => {
      if (recorderRef.current?.state === 'recording') {
        recorderRef.current.onstop = null
        recorderRef.current.stop()
      }
      releaseStream()
      revokeUrl()
    },
    [releaseStream, revokeUrl]
  )

  return { state, elapsed, recording, error, start, stop, reset }
}
