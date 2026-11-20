import { ScanFace } from 'lucide-react'

import { EmptyState } from '../../../components/ui'

interface Props {
  onStart?: () => void
}

export default function FaceSwapEmptyState({ onStart }: Props) {
  return (
    <EmptyState
      icon={<ScanFace size={24} aria-hidden="true" />}
      title="Aún no has creado videos"
      description="Sube tu foto, elige una plantilla y genera tu primer video."
      actionLabel={onStart ? 'Empezar por tu foto' : undefined}
      onAction={onStart}
    />
  )
}
