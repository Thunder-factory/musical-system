import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { Link } from 'react-router-dom'
import { RotateCcw, Upload } from 'lucide-react'

import { Button, Input } from '../../../components/ui'
import { useAudioRecorder } from '../hooks/useAudioRecorder'
import {
  formatSeconds,
  HUMMING_CREDIT_COST,
  MAX_HUMMING_SECONDS,
  MIN_HUMMING_SECONDS,
} from '../lib/humming-constants'
import { HummingRecorderMeter } from './humming-recorder-meter'
import InspirationPanel from './inspiration-panel'

interface HummingRecorderCardProps {
  busy: boolean
  submitError: string | null
  noCredits: boolean
  onSubmit: (file: File, title: string) => Promise<boolean>
}

export default function HummingRecorderCard({
  busy,
  submitError,
  noCredits,
  onSubmit,
}: HummingRecorderCardProps) {
  const recorder = useAudioRecorder(MAX_HUMMING_SECONDS)
  const [uploaded, setUploaded] = useState<File | null>(null)
  const [uploadedUrl, setUploadedUrl] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [sending, setSending] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(
    () => () => {
      if (uploadedUrl) {
        URL.revokeObjectURL(uploadedUrl)
      }
    },
    [uploadedUrl]
  )

  const isRecording = recorder.state === 'recording'
  const source = uploaded ?? recorder.recording?.file ?? null
  const previewUrl = uploadedUrl ?? recorder.recording?.url ?? null
  const tooShort =
    !uploaded && recorder.recording !== null && recorder.recording.seconds < MIN_HUMMING_SECONDS
  const canSubmit = Boolean(source) && !tooShort && !busy && !sending && !isRecording

  function clearUpload() {
    setUploaded(null)
    setUploadedUrl(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  async function handleRecordClick() {
    if (isRecording) {
      recorder.stop()
      return
    }
    clearUpload()
    await recorder.start()
  }

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    recorder.reset()
    setUploaded(file)
    setUploadedUrl(URL.createObjectURL(file))
  }

  async function handleSubmit() {
    if (!source || !canSubmit) {
      return
    }
    setSending(true)
    const ok = await onSubmit(source, title)
    setSending(false)
    if (ok) {
      recorder.reset()
      clearUpload()
      setTitle('')
    }
  }

  return (
    <section
      className="flex flex-col gap-5 rounded-2xl border border-border bg-card p-5 sm:p-6"
      aria-labelledby="humming-recorder-title"
    >
      <HummingRecorderMeter
        state={recorder.state}
        elapsed={recorder.elapsed}
        disabled={busy || sending}
        onRecordClick={() => void handleRecordClick()}
      />

      <p className="text-sm text-muted">
        Tararea con «na-na» o «la-la» en un lugar tranquilo. Detectamos melodía, ritmo y tonalidad
        para crear versiones en distintos estilos.
      </p>

      <InspirationPanel
        disabled={busy || sending || isRecording}
        onRecord={() => {
          if (!isRecording) {
            void handleRecordClick()
          }
        }}
      />

      {previewUrl && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-white">
            {uploaded
              ? uploaded.name
              : `Tu grabación (${formatSeconds(recorder.recording?.seconds ?? 0)})`}
          </p>
          <audio controls src={previewUrl} className="w-full" />
          {tooShort && (
            <p className="text-xs text-warning">
              La grabación es muy corta: graba al menos {MIN_HUMMING_SECONDS} segundos.
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.webm,.ogg,.m4a,.mp4,.mp3,.wav,.aac,.flac"
          onChange={handleFile}
          className="sr-only"
          id="humming-file"
          disabled={busy || isRecording}
        />
        <Button
          variant="secondary"
          size="sm"
          disabled={busy || isRecording}
          onClick={() => fileInputRef.current?.click()}
          leftIcon={<Upload size={14} aria-hidden="true" />}
        >
          Subir archivo de audio
        </Button>
        {(recorder.recording || uploaded) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              recorder.reset()
              clearUpload()
            }}
            leftIcon={<RotateCcw size={14} aria-hidden="true" />}
          >
            Descartar
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Input
          id="humming-title"
          aria-label="Título (opcional)"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={200}
          placeholder="Título (opcional)"
          className="flex-1"
        />
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit}
          loading={sending}
          costCredits={HUMMING_CREDIT_COST}
        >
          Crear canciones
        </Button>
      </div>

      {(recorder.error || submitError) && (
        <p className="text-sm text-error" role="alert">
          {recorder.error ?? submitError}{' '}
          {noCredits && (
            <Link to="/payments" className="font-semibold text-primary underline">
              Recargar créditos
            </Link>
          )}
        </p>
      )}
    </section>
  )
}
