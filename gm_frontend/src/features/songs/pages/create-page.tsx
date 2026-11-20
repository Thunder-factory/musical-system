import { useCallback, useState, type FormEvent } from 'react'

import { FormField, Input, Textarea } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import CreateModeTabs from '../components/create-mode-tabs'
import CreateOptionsPanel from '../components/create-options-panel'
import CreatePreviewCard from '../components/create-preview-card'
import StyleTagPicker, { type SelectedTagsMap } from '../components/style-tag-picker'
import { useCreateSongJob } from '../hooks/useCreateSongJob'
import { buildCreateSongPayload, validateCreateForm } from '../lib/create-song-form'
import type { CreateMode, SongLanguage, VocalType } from '../lib/create-song-options'

const INITIAL_TAGS: SelectedTagsMap = { genres: [], moods: [], tempo: [] }

export default function CreatePage() {
  const user = useAuthStore((s) => s.user)

  const [mode, setMode] = useState<CreateMode>('description')
  const [duration, setDuration] = useState(40)
  const [vocalType, setVocalType] = useState<VocalType>('auto')
  const [language, setLanguage] = useState<SongLanguage>('es')
  const [guidanceScale, setGuidanceScale] = useState(10)
  const [inferStep, setInferStep] = useState(100)

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [prompt, setPrompt] = useState('')
  const [lyrics, setLyrics] = useState('')
  const [describedLyrics, setDescribedLyrics] = useState('')
  const [selectedTags, setSelectedTags] = useState<SelectedTagsMap>(INITIAL_TAGS)

  const handleRecoverTitle = useCallback((recovered: string) => setTitle(recovered), [])
  const { stage, ready, errorMsg, setErrorMsg, submitGeneration, resetJob } = useCreateSongJob(
    title,
    handleRecoverTitle
  )

  const selectedTagValues = Object.values(selectedTags).flat()
  const isBusy = stage === 'submitting' || stage === 'polling'

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = {
      mode,
      title,
      description,
      prompt,
      lyrics,
      describedLyrics,
      selectedTagValues,
      duration,
      vocalType,
      language,
      guidanceScale,
      inferStep,
    }
    const validationError = validateCreateForm(values)
    if (validationError) {
      setErrorMsg(validationError)
      return
    }
    void submitGeneration(buildCreateSongPayload(values))
  }

  function handleReset() {
    resetJob()
    setTitle('')
    setDescription('')
    setPrompt('')
    setLyrics('')
    setDescribedLyrics('')
    setSelectedTags(INITIAL_TAGS)
  }

  return (
    <div className="min-h-full px-4 pb-20 pt-6 sm:px-8">
      <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-6">
        <header>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Crear canción</h1>
          <p className="mt-1 text-sm text-muted">Describe tu idea y conviértela en canción.</p>
        </header>

        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.75fr)]">
          <form
            id="create-song-form"
            onSubmit={handleSubmit}
            noValidate
            className="flex flex-col gap-5 rounded-2xl border border-border bg-card p-5"
          >
            <CreateModeTabs
              mode={mode}
              disabled={isBusy}
              onChange={(nextMode) => {
                setMode(nextMode)
                setErrorMsg(null)
              }}
            />

            <CreateOptionsPanel
              duration={duration}
              vocalType={vocalType}
              language={language}
              guidanceScale={guidanceScale}
              inferStep={inferStep}
              disabled={isBusy}
              onDurationChange={setDuration}
              onVocalTypeChange={setVocalType}
              onLanguageChange={setLanguage}
              onGuidanceScaleChange={setGuidanceScale}
              onInferStepChange={setInferStep}
            />

            <FormField label="Título" required>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ej. Ecos de medianoche"
                disabled={isBusy}
                maxLength={200}
              />
            </FormField>

            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-muted">Etiquetas de estilo</span>
              <StyleTagPicker
                selected={selectedTags}
                disabled={isBusy}
                onChange={(group, values) =>
                  setSelectedTags((current) => ({ ...current, [group]: values }))
                }
              />
            </div>

            {mode === 'description' ? (
              <FormField label="Describe tu canción" hint="Cuenta la escena, emoción o historia." required>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Ej. Un viaje nocturno entre soledad y esperanza con sintetizadores cálidos..."
                  rows={4}
                  disabled={isBusy}
                />
              </FormField>
            ) : (
              <FormField label="Estilo musical" hint="Combina estilos e instrumentos.">
                <Input
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Ej. Synthwave oscuro con bajo potente..."
                  disabled={isBusy}
                />
              </FormField>
            )}

            {mode === 'exact_lyrics' && (
              <FormField label="Tu letra" hint="La música se adaptará exactamente a esta letra." required>
                <Textarea
                  value={lyrics}
                  onChange={(e) => setLyrics(e.target.value)}
                  placeholder="Escribe aquí la letra completa..."
                  rows={6}
                  disabled={isBusy}
                />
              </FormField>
            )}

            {mode === 'auto_lyrics' && (
              <FormField label="Idea para la letra" hint="Tema, historia o mensaje." required>
                <Textarea
                  value={describedLyrics}
                  onChange={(e) => setDescribedLyrics(e.target.value)}
                  placeholder="Ej. Dos personas se separan, pero esperan reencontrarse bajo las estrellas..."
                  rows={4}
                  disabled={isBusy}
                />
              </FormField>
            )}

            {errorMsg && stage === 'idle' && (
              <p role="alert" className="text-sm text-error">
                {errorMsg}
              </p>
            )}
          </form>

          <CreatePreviewCard
            title={title}
            credits={user?.credit_balance ?? 0}
            mode={mode}
            duration={duration}
            vocalType={vocalType}
            language={language}
            selectedTagCount={selectedTagValues.length}
            stage={stage}
            ready={ready}
            errorMsg={errorMsg}
            onReset={handleReset}
          />
        </div>
      </div>
    </div>
  )
}
