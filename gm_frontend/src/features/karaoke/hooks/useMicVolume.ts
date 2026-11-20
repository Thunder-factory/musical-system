import { useEffect, useRef, useState } from 'react'

function getRmsVolume(analyser: AnalyserNode): number {
  const buf = new Uint8Array(analyser.frequencyBinCount)
  analyser.getByteTimeDomainData(buf)
  let sum = 0
  for (let i = 0; i < buf.length; i++) {
    const n = buf[i] / 128 - 1
    sum += n * n
  }
  return Math.sqrt(sum / buf.length)
}

export function useMicVolume(ended: boolean) {
  const analyserRef = useRef<AnalyserNode | null>(null)
  const micStreamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const [ownVolume, setOwnVolume] = useState(0)

  useEffect(() => {
    let stopped = false
    let interval: ReturnType<typeof setInterval> | null = null

    navigator.mediaDevices
      ?.getUserMedia({ audio: true, video: false })
      .then((s) => {
        if (stopped) {
          s.getTracks().forEach((t) => t.stop())
          return
        }
        micStreamRef.current = s
        const ctx = new AudioContext()
        audioCtxRef.current = ctx
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 256
        ctx.createMediaStreamSource(s).connect(analyser)
        analyserRef.current = analyser
        interval = setInterval(() => {
          if (analyserRef.current) {
            setOwnVolume(getRmsVolume(analyserRef.current))
          }
        }, 150)
      })
      .catch(() => {})

    return () => {
      stopped = true
      if (interval) {
        clearInterval(interval)
      }
      micStreamRef.current?.getTracks().forEach((t) => t.stop())
      audioCtxRef.current?.close().catch(() => {})
    }
  }, [])

  useEffect(() => {
    if (!ended) {
      return
    }
    micStreamRef.current?.getTracks().forEach((t) => t.stop())
    micStreamRef.current = null
    audioCtxRef.current?.close().catch(() => {})
    audioCtxRef.current = null
    analyserRef.current = null
    setOwnVolume(0)
  }, [ended])

  return ownVolume
}
