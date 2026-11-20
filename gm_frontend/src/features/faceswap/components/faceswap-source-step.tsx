import type { FaceSwapSourceMode, FaceSwapTemplate, FaceTarget } from '../types/faceswap.types'
import ClipUploader from './clip-uploader'
import FaceSwapStep from './faceswap-step'
import FaceTargetPicker from './face-target-picker'
import SourceTabs from './source-tabs'
import TemplateGrid from './template-grid'

interface Props {
  templates: FaceSwapTemplate[]
  templatesLoading: boolean
  templatesError: string | null
  onRetryTemplates: () => void
  mode: FaceSwapSourceMode
  onModeChange: (mode: FaceSwapSourceMode) => void
  templateId: string | null
  onTemplateChange: (id: string) => void
  clip: File | null
  clipUrl: string | null
  onClipChange: (file: File | null) => void
  videoSrc: string | null
  sourceKey: string | null
  target: FaceTarget | null
  onTargetChange: (target: FaceTarget | null) => void
  disabled: boolean
}

export default function FaceSwapSourceStep(props: Props) {
  const { mode, disabled, videoSrc } = props
  return (
    <FaceSwapStep
      number={2}
      title="Video base"
      hint="Elige una plantilla o sube un clip propio."
      done={Boolean(videoSrc)}
    >
      <SourceTabs mode={mode} onModeChange={props.onModeChange} disabled={disabled}>
        {mode === 'catalog' ? (
          <TemplateGrid
            templates={props.templates}
            isLoading={props.templatesLoading}
            isError={Boolean(props.templatesError)}
            errorMessage={props.templatesError ?? undefined}
            selectedId={props.templateId}
            onSelect={props.onTemplateChange}
            onRetry={props.onRetryTemplates}
            onUseOwnClip={() => props.onModeChange('own')}
            disabled={disabled}
          />
        ) : (
          <ClipUploader
            file={props.clip}
            previewUrl={props.clipUrl}
            onChange={props.onClipChange}
            disabled={disabled}
          />
        )}
      </SourceTabs>

      {videoSrc && (
        <div className="flex flex-col gap-3 border-t border-border pt-3">
          <div>
            <h3 className="text-sm font-bold text-white">¿A quién le cambiamos la cara?</h3>
            <p className="mt-0.5 text-xs text-muted">
              Opcional. Útil si aparece más de una persona.
            </p>
          </div>
          <FaceTargetPicker
            key={props.sourceKey ?? videoSrc}
            src={videoSrc}
            value={props.target}
            onChange={props.onTargetChange}
            disabled={disabled}
          />
        </div>
      )}
    </FaceSwapStep>
  )
}
