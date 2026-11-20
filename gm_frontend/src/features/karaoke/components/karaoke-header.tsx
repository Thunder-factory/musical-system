import { Upload, UsersRound } from 'lucide-react'

import { Badge, Button } from '../../../components/ui'

interface KaraokeHeaderProps {
  showUpload: boolean
  firebaseReady: boolean
  onOpenUpload: () => void
  onOpenJoin: () => void
}

export default function KaraokeHeader({
  showUpload,
  firebaseReady,
  onOpenUpload,
  onOpenJoin,
}: KaraokeHeaderProps) {
  return (
    <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Karaoke</h1>
        <p className="mt-1 text-sm text-muted">
          Elige una canción y canta con su pista instrumental.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2.5">
        {showUpload && (
          <Button variant="primary" leftIcon={<Upload size={15} />} onClick={onOpenUpload}>
            Subir música
          </Button>
        )}

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            leftIcon={<UsersRound size={15} />}
            onClick={onOpenJoin}
            disabled={!firebaseReady}
            title={
              firebaseReady
                ? 'Ingresar a una sala con código'
                : 'Las salas en vivo requieren configuración en tiempo real. Disponible próximamente.'
            }
          >
            Unirse a sala
          </Button>
          {!firebaseReady && <Badge variant="warning">Próximamente</Badge>}
        </div>
      </div>
    </header>
  )
}
