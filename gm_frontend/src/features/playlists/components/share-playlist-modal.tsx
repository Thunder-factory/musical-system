import { useState } from 'react'
import { Check, Copy, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button, Input, Modal } from '../../../components/ui'
import { toast } from '../../../store/toast.store'

interface SharePlaylistModalProps {
  open: boolean
  sharePath: string | null
  onClose: () => void
}

export default function SharePlaylistModal({
  open,
  sharePath,
  onClose,
}: SharePlaylistModalProps) {
  const [copied, setCopied] = useState(false)
  const fullUrl = sharePath ? new URL(sharePath, window.location.origin).href : ''

  async function handleCopy() {
    if (!fullUrl) {
      return
    }
    try {
      await navigator.clipboard.writeText(fullUrl)
      setCopied(true)
      toast.success('Enlace copiado al portapapeles')
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('No se pudo copiar automáticamente')
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Compartir playlist" size="sm">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          Cualquier persona con este enlace podrá ver esta playlist pública.
        </p>

        <div className="flex items-center gap-2">
          <Input value={fullUrl} readOnly aria-label="Enlace público de la playlist" />
          <Button
            variant="primary"
            size="sm"
            leftIcon={copied ? <Check size={14} /> : <Copy size={14} />}
            onClick={() => void handleCopy()}
          >
            {copied ? 'Copiado' : 'Copiar'}
          </Button>
        </div>

        {sharePath && (
          <Link
            to={sharePath}
            onClick={onClose}
            className="inline-flex items-center gap-1.5 self-start text-xs font-semibold text-primary hover:underline"
          >
            <ExternalLink size={13} aria-hidden="true" />
            Abrir vista pública
          </Link>
        )}
      </div>
    </Modal>
  )
}
