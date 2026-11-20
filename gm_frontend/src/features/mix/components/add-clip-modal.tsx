import { useEffect, useState } from 'react'
import { isAxiosError } from 'axios'

import { Modal } from '../../../components/ui'
import { getLibrary, getSongDetail, type LibrarySong } from '../../songs/api/songs.api'
import { getStemDownloadUrl, getStemJobs, type StemJob } from '../../stems/api/stems.api'
import { addClip, uploadExternalClip, type MixClip } from '../api/mix.api'
import LibraryClipTab from './library-clip-tab'
import StemsClipTab from './stems-clip-tab'
import UploadClipTab from './upload-clip-tab'

interface AddClipModalProps {
  open: boolean
  mixId: string
  nextPosition: number
  onAdd: (clip: MixClip) => void
  onClose: () => void
}

type SourceTab = 'library' | 'stems' | 'external'

function getErrorMessage(error: unknown, fallback: string) {
  if (isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail ?? fallback
  }
  return error instanceof Error ? error.message : fallback
}

function loadStemDurationMs(stemFileId: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const audio = new Audio()
    audio.preload = 'metadata'
    const cleanup = () => {
      audio.removeAttribute('src')
      audio.load()
    }
    audio.onloadedmetadata = () => {
      const durationMs = Math.round(audio.duration * 1000)
      cleanup()
      if (Number.isFinite(durationMs) && durationMs > 0) {
        resolve(durationMs)
      } else {
        reject(new Error('No se pudo determinar la duración de la pista.'))
      }
    }
    audio.onerror = () => {
      cleanup()
      reject(new Error('No se pudo leer la duración de la pista.'))
    }
    void getStemDownloadUrl(stemFileId)
      .then((url) => {
        audio.src = url
        audio.load()
      })
      .catch((error) => {
        cleanup()
        reject(error)
      })
  })
}

export default function AddClipModal({
  open,
  mixId,
  nextPosition,
  onAdd,
  onClose,
}: AddClipModalProps) {
  const [tab, setTab] = useState<SourceTab>('library')
  const [songs, setSongs] = useState<LibrarySong[]>([])
  const [stemJobs, setStemJobs] = useState<StemJob[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [externalProgress, setExternalProgress] = useState<number | null>(null)

  useEffect(() => {
    if (!open) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([getLibrary(), getStemJobs()])
      .then(([s, j]) => {
        setSongs(s)
        setStemJobs(j)
      })
      .catch(() => setError('No se pudieron cargar tus pistas disponibles.'))
      .finally(() => setLoading(false))
  }, [open])

  async function handleAddSong(song: LibrarySong) {
    setAdding(true)
    setError(null)
    try {
      const detail = await getSongDetail(song.id)
      if (!detail.audio_duration || detail.audio_duration <= 0) {
        throw new Error('La canción no tiene una duración válida.')
      }
      const clip = await addClip(mixId, {
        song_id: song.id,
        position: nextPosition,
        start_time_ms: 0,
        end_time_ms: Math.round(detail.audio_duration * 1000),
      })
      onAdd(clip)
    } catch (err) {
      setError(getErrorMessage(err, 'Error al agregar el clip.'))
    } finally {
      setAdding(false)
    }
  }

  async function handleAddStem(stemFileId: string, durationMs?: number) {
    setAdding(true)
    setError(null)
    try {
      const resolvedMs =
        durationMs && durationMs > 0 ? Math.round(durationMs) : await loadStemDurationMs(stemFileId)
      const clip = await addClip(mixId, {
        stem_file_id: stemFileId,
        position: nextPosition,
        start_time_ms: 0,
        end_time_ms: resolvedMs,
      })
      onAdd(clip)
    } catch (err) {
      setError(getErrorMessage(err, 'Error al agregar la pista.'))
    } finally {
      setAdding(false)
    }
  }

  async function handleUploadExternal(file: File, durationMs: number) {
    setAdding(true)
    setExternalProgress(0)
    setError(null)
    try {
      const clip = await uploadExternalClip(
        mixId,
        { file, position: nextPosition, start_time_ms: 0, end_time_ms: durationMs },
        setExternalProgress
      )
      onAdd(clip)
    } catch (err) {
      setError(getErrorMessage(err, 'Error al subir el archivo.'))
    } finally {
      setAdding(false)
      setExternalProgress(null)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Agregar clip" size="lg" preventClose={adding}>
      <div className="-mx-5 -mt-5 mb-4 flex border-b border-border sm:-mx-6">
        {(
          [
            ['library', 'Biblioteca'],
            ['stems', 'Stems separados'],
            ['external', 'Archivo externo'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            disabled={adding}
            onClick={() => setTab(key)}
            className={`flex-1 border-b-2 py-2.5 text-sm transition-colors ${
              tab === key
                ? 'border-primary font-bold text-white'
                : 'border-transparent text-muted hover:text-white'
            } disabled:cursor-not-allowed disabled:opacity-60`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <div
          role="alert"
          className="mb-3 rounded-lg border border-error-border bg-error-soft px-3.5 py-2 text-xs text-error"
        >
          {error}
        </div>
      )}

      <div className="max-h-[52vh] overflow-y-auto">
        {loading && tab !== 'external' ? (
          <p className="py-8 text-center text-sm text-muted">Cargando...</p>
        ) : tab === 'external' ? (
          <UploadClipTab
            adding={adding}
            progress={externalProgress}
            onError={setError}
            onUpload={handleUploadExternal}
          />
        ) : tab === 'library' ? (
          <LibraryClipTab songs={songs} adding={adding} onSelectSong={handleAddSong} />
        ) : (
          <StemsClipTab stemJobs={stemJobs} adding={adding} onSelectStem={handleAddStem} />
        )}
      </div>
    </Modal>
  )
}
