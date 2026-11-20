import { useState } from 'react'

import { useObjectUrl } from '../../hooks/useObjectUrl'
import { useAuthStore } from '../../store/auth.store'
import { FACESWAP_CREDIT_COST } from '../../types/faceswap.types'
import type {
  CreateFaceSwapJobInput,
  FaceSwapSourceMode,
  FaceSwapTemplate,
  FaceTarget,
} from '../../types/faceswap.types'
import ConsentCheck from './consent-check'
import FaceSwapSourceStep from './faceswap-source-step'
import FaceSwapStep from './faceswap-step'
import FaceSwapSubmitBar from './faceswap-submit-bar'
import PhotoPicker from './photo-picker'

interface Props {
  templates: FaceSwapTemplate[]
  templatesLoading: boolean
  templatesError: string | null
  onRetryTemplates: () => void
  submitting: boolean
  processing: boolean
  apiNoCredits: boolean
  error: string | null
  onSubmit: (input: CreateFaceSwapJobInput) => void
}

/** Formulario de 3 pasos: foto, video base (+ personaje opcional) y confirmación. */
export default function FaceSwapForm(props: Props) {
  const { templates, submitting, processing } = props
  const [photo, setPhoto] = useState<File | null>(null)
  const [mode, setMode] = useState<FaceSwapSourceMode>('catalog')
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [clip, setClip] = useState<File | null>(null)
  // El personaje queda atado a la fuente en que se eligió (plantilla o archivo, no a la URL
  // firmada, que cambia en cada refetch): si cambia la fuente, se descarta.
  const [picked, setPicked] = useState<{ key: string; target: FaceTarget } | null>(null)
  const [consent, setConsent] = useState(false)
  const clipUrl = useObjectUrl(clip)
  const balance = useAuthStore((s) => s.user?.credit_balance ?? 0)

  const locked = submitting || processing
  const selectedTemplate = templates.find((t) => t.id === templateId)
  const videoSrc = mode === 'catalog' ? (selectedTemplate?.preview_url ?? null) : clipUrl
  const sourceKey = mode === 'catalog' ? (selectedTemplate?.id ?? null) : clipUrl
  const target = picked && picked.key === sourceKey ? picked.target : null
  const hasSource = mode === 'catalog' ? Boolean(selectedTemplate) : Boolean(clip)
  const missing = !photo
    ? 'Falta subir tu foto.'
    : !hasSource
      ? mode === 'catalog'
        ? 'Falta elegir una plantilla.'
        : 'Falta subir tu clip.'
      : !consent
        ? 'Falta confirmar el permiso de la foto.'
        : null

  function submit() {
    if (!photo || missing) {
      return
    }
    props.onSubmit({
      photo,
      consent,
      ...(mode === 'catalog' ? { templateId: selectedTemplate?.id } : { video: clip ?? undefined }),
      ...(target ? { target } : {}),
    })
  }

  return (
    <div className="flex flex-col gap-4">
      <FaceSwapStep
        number={1}
        title="Tu foto"
        hint="Una sola cara, de frente y bien iluminada."
        done={Boolean(photo)}
      >
        <PhotoPicker file={photo} onChange={setPhoto} disabled={locked} />
      </FaceSwapStep>

      <FaceSwapSourceStep
        templates={templates}
        templatesLoading={props.templatesLoading}
        templatesError={props.templatesError}
        onRetryTemplates={props.onRetryTemplates}
        mode={mode}
        onModeChange={setMode}
        templateId={templateId}
        onTemplateChange={setTemplateId}
        clip={clip}
        clipUrl={clipUrl}
        onClipChange={setClip}
        videoSrc={videoSrc}
        sourceKey={sourceKey}
        target={target}
        onTargetChange={(t) => setPicked(t && sourceKey ? { key: sourceKey, target: t } : null)}
        disabled={locked}
      />

      <FaceSwapStep number={3} title="Confirma y genera" done={!missing}>
        <ConsentCheck checked={consent} onChange={setConsent} disabled={locked} />
        <FaceSwapSubmitBar
          canSubmit={!missing}
          submitting={submitting}
          processing={processing}
          noCredits={props.apiNoCredits || balance < FACESWAP_CREDIT_COST}
          missing={missing}
          error={props.error}
          onSubmit={submit}
        />
      </FaceSwapStep>
    </div>
  )
}
