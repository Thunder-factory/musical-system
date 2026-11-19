import { useState } from 'react'

import { useAuthStore } from '../../store/auth.store'
import { FACESWAP_CREDIT_COST } from '../../types/faceswap.types'
import type {
  CreateFaceSwapJobInput,
  FaceSwapSourceMode,
  FaceSwapTemplate,
} from '../../types/faceswap.types'
import ClipUploader from './clip-uploader'
import ConsentCheck from './consent-check'
import FaceSwapStep from './faceswap-step'
import FaceSwapSubmitBar from './faceswap-submit-bar'
import PhotoPicker from './photo-picker'
import SourceTabs from './source-tabs'
import TemplateGrid from './template-grid'

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

/** Formulario de 3 pasos: foto, video base (plantilla o clip) y confirmación. */
export default function FaceSwapForm(props: Props) {
  const { templates, submitting, processing } = props
  const [photo, setPhoto] = useState<File | null>(null)
  const [mode, setMode] = useState<FaceSwapSourceMode>('catalog')
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [clip, setClip] = useState<File | null>(null)
  const [consent, setConsent] = useState(false)
  const balance = useAuthStore((s) => s.user?.credit_balance ?? 0)

  const locked = submitting || processing
  const selectedTemplate = templates.find((t) => t.id === templateId)
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

      <FaceSwapStep
        number={2}
        title="Video base"
        hint="Elige una plantilla o sube un clip propio."
        done={hasSource}
      >
        <SourceTabs mode={mode} onModeChange={setMode} disabled={locked}>
          {mode === 'catalog' ? (
            <TemplateGrid
              templates={templates}
              isLoading={props.templatesLoading}
              isError={Boolean(props.templatesError)}
              errorMessage={props.templatesError ?? undefined}
              selectedId={templateId}
              onSelect={setTemplateId}
              onRetry={props.onRetryTemplates}
              onUseOwnClip={() => setMode('own')}
              disabled={locked}
            />
          ) : (
            <ClipUploader file={clip} onChange={setClip} disabled={locked} />
          )}
        </SourceTabs>
      </FaceSwapStep>

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
